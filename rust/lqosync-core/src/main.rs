use anyhow::Context;
use clap::Parser;
use lqosync_core::atomic_state::{append_audit_jsonl_payload, atomic_write_json_state_payload, atomic_write_text_payload, validate_json_state_payload};
use lqosync_core::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use lqosync_core::circuits::normalize_circuits_payload;
use lqosync_core::diff::{diff_files_payload, diff_network_text, diff_shaped_devices_text};
use lqosync_core::network::{collect_node_names, parse_network_text, validate_network};
use lqosync_core::policy::evaluate_policy_payload;
use lqosync_core::protocol::{CoreRequest, CoreResponse, PROTOCOL_VERSION};
use lqosync_core::shaped_devices::{parse_csv_text, render_csv_text, validate_rows};
use lqosync_core::sync_plan::evaluate_sync_plan_payload;
use lqosync_core::validators::{validate_collector_output_payload, validate_config_value, validate_files_payload};
use serde_json::{json, Value};
use std::io::{self, Read, Write};
use std::path::Path;
use std::time::Instant;

#[cfg(unix)]
use std::os::unix::net::{UnixListener, UnixStream};

#[derive(Parser, Debug)]
#[command(name = "lqosync-core", version, about = "Rust safety core for LQoSync")]
struct Args {
    /// Read a JSON protocol request from stdin. This is the default CLI behavior.
    #[arg(long, default_value_t = true)]
    json: bool,

    /// Run as a Unix socket daemon. The daemon uses the same JSON protocol as stdin/stdout.
    #[arg(long, default_value_t = false)]
    daemon: bool,

    /// Unix socket path for daemon mode.
    #[arg(long, default_value = "/run/lqosync-core.sock")]
    socket: String,
}

fn main() {
    let args = Args::parse();
    if args.daemon {
        if let Err(e) = run_daemon(&args.socket) {
            eprintln!("lqosync-core daemon failed: {e}");
            std::process::exit(1);
        }
        return;
    }
    run_one_shot();
}

fn run_one_shot() {
    let started = Instant::now();
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        let response = CoreResponse::failure("unknown", None, "stdin_read_failed", format!("Failed to read stdin: {e}"), started);
        print_response(&response);
        std::process::exit(1);
    }

    let response = handle_request_text(&input, started);
    let exit_code = if response.ok { 0 } else { 2 };
    print_response(&response);
    std::process::exit(exit_code);
}

#[cfg(unix)]
fn run_daemon(socket_path: &str) -> anyhow::Result<()> {
    let path = Path::new(socket_path);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create socket parent {}", parent.display()))?;
    }
    if path.exists() {
        std::fs::remove_file(path).with_context(|| format!("remove stale socket {}", path.display()))?;
    }
    let listener = UnixListener::bind(path).with_context(|| format!("bind unix socket {}", path.display()))?;
    eprintln!("lqosync-core daemon listening on {socket_path}");
    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                if let Err(e) = handle_daemon_stream(&mut stream) {
                    let started = Instant::now();
                    let response = CoreResponse::failure("unknown", None, "daemon_stream_failed", e.to_string(), started);
                    let _ = write_response_to_stream(&mut stream, &response);
                }
            }
            Err(e) => eprintln!("lqosync-core daemon accept failed: {e}"),
        }
    }
    Ok(())
}

#[cfg(not(unix))]
fn run_daemon(_socket_path: &str) -> anyhow::Result<()> {
    anyhow::bail!("daemon mode is only supported on Unix platforms")
}

#[cfg(unix)]
fn handle_daemon_stream(stream: &mut UnixStream) -> anyhow::Result<()> {
    let started = Instant::now();
    let mut input = String::new();
    stream.read_to_string(&mut input)?;
    let response = handle_request_text(&input, started);
    write_response_to_stream(stream, &response)?;
    Ok(())
}

#[cfg(unix)]
fn write_response_to_stream(stream: &mut UnixStream, response: &CoreResponse) -> anyhow::Result<()> {
    let text = serde_json::to_string(response)?;
    stream.write_all(text.as_bytes())?;
    stream.write_all(b"\n")?;
    stream.flush()?;
    Ok(())
}

fn handle_request_text(input: &str, started: Instant) -> CoreResponse {
    let req: CoreRequest = match serde_json::from_str(input) {
        Ok(req) => req,
        Err(e) => return CoreResponse::failure("unknown", None, "invalid_request_json", format!("Invalid request JSON: {e}"), started),
    };
    match handle_request(&req, started) {
        Ok(response) => response,
        Err(e) => CoreResponse::failure(req.op.clone(), req.request_id.clone(), "operation_failed", e.to_string(), started),
    }
}

fn handle_request(req: &CoreRequest, started: Instant) -> anyhow::Result<CoreResponse> {
    if req.version != PROTOCOL_VERSION {
        return Ok(CoreResponse::failure(
            req.op.clone(),
            req.request_id.clone(),
            "unsupported_protocol_version",
            format!("Unsupported protocol version {}; expected {}", req.version, PROTOCOL_VERSION),
            started,
        ));
    }

    match req.op.as_str() {
        "health" => Ok(CoreResponse::success(req, json!({
            "status": "ok",
            "mode": "daemon_or_cli",
            "protocol_version": PROTOCOL_VERSION,
            "operations": [
                "health",
                "parse-bandwidth",
                "validate-config",
                "validate-shaped-devices",
                "validate-network",
                "validate-files",
                "validate-collector-output",
                "diff-shaped-devices",
                "diff-network",
                "diff-files",
                "validate-json-state",
                "write-json-state",
                "write-text-file",
                "append-audit-jsonl",
                "evaluate-policy",
                "normalize-circuits",
                "evaluate-sync-plan"
            ]
        }), started)),
        "parse-bandwidth" => Ok(handle_parse_bandwidth(req, started)),
        "validate-config" => Ok(handle_validate_config(req, started)),
        "validate-shaped-devices" => Ok(handle_validate_shaped_devices(req, started)?),
        "validate-network" => Ok(handle_validate_network(req, started)?),
        "validate-files" => {
            let (result, errors, warnings) = validate_files_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "validate-collector-output" => {
            let (result, errors, warnings) = validate_collector_output_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "diff-shaped-devices" => {
            let current = req.payload.get("current_csv_text").and_then(Value::as_str).unwrap_or("");
            let proposed = req.payload.get("proposed_csv_text").and_then(Value::as_str).unwrap_or("");
            let (result, errors, warnings) = diff_shaped_devices_text(current, proposed);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "diff-network" => {
            let current = req.payload.get("current_network_text").and_then(Value::as_str).unwrap_or("{}");
            let proposed = req.payload.get("proposed_network_text").and_then(Value::as_str).unwrap_or("{}");
            let (result, errors, warnings) = diff_network_text(current, proposed);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "diff-files" => {
            let (result, errors, warnings) = diff_files_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "validate-json-state" => {
            let (result, errors, warnings) = validate_json_state_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "write-json-state" => {
            let result = atomic_write_json_state_payload(&req.payload)?;
            Ok(CoreResponse::success(req, result, started))
        }
        "write-text-file" => {
            let result = atomic_write_text_payload(&req.payload)?;
            Ok(CoreResponse::success(req, result, started))
        }
        "append-audit-jsonl" => {
            let result = append_audit_jsonl_payload(&req.payload)?;
            Ok(CoreResponse::success(req, result, started))
        }
        "evaluate-policy" => {
            let (result, errors, warnings) = evaluate_policy_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "normalize-circuits" => {
            let (result, errors, warnings) = normalize_circuits_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "evaluate-sync-plan" => {
            let (result, errors, warnings) = evaluate_sync_plan_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        other => Ok(CoreResponse::failure(
            other,
            req.request_id.clone(),
            "unknown_operation",
            format!("Unknown operation: {other}"),
            started,
        )),
    }
}

fn handle_parse_bandwidth(req: &CoreRequest, started: Instant) -> CoreResponse {
    let parser = req.payload.get("parser").and_then(Value::as_str).unwrap_or("unit");
    let value = req.payload.get("value").and_then(Value::as_str).unwrap_or("");
    let result = match parser {
        "rate_limit" => {
            let parsed = parse_rate_limit(value);
            json!({"download_mbps": parsed.download_mbps, "upload_mbps": parsed.upload_mbps})
        }
        "comment" => match parse_comment_bandwidth(value) {
            Some(parsed) => json!({"matched": true, "download_mbps": parsed.download_mbps, "upload_mbps": parsed.upload_mbps}),
            None => json!({"matched": false}),
        },
        _ => json!({"mbps": convert_to_mbps(value)}),
    };
    CoreResponse::success(req, result, started)
}

fn handle_validate_config(req: &CoreRequest, started: Instant) -> CoreResponse {
    let config = req.payload.get("config").unwrap_or(&req.payload);
    let (errors, warnings) = validate_config_value(config);
    CoreResponse::validation(req, json!({"write_allowed": errors.is_empty(), "apply_allowed": errors.is_empty()}), errors, warnings, started)
}

fn handle_validate_shaped_devices(req: &CoreRequest, started: Instant) -> anyhow::Result<CoreResponse> {
    let csv_text = if let Some(text) = req.payload.get("csv_text").and_then(Value::as_str) {
        text.to_string()
    } else if let Some(path) = req.payload.get("shaped_devices_csv_path").and_then(Value::as_str) {
        std::fs::read_to_string(path).context("read ShapedDevices.csv")?
    } else {
        String::new()
    };
    let network_mode = req.payload.get("network_mode").and_then(Value::as_str).unwrap_or("router_children");
    let rows = parse_csv_text(&csv_text).context("parse shaped devices CSV")?;
    let (errors, warnings) = validate_rows(&rows, network_mode, None);
    let rendered = if req.payload.get("render").and_then(Value::as_bool).unwrap_or(false) {
        Some(render_csv_text(&rows).context("render shaped devices CSV")?)
    } else {
        None
    };
    Ok(CoreResponse::validation(
        req,
        json!({"row_count": rows.len(), "rendered_csv": rendered}),
        errors,
        warnings,
        started,
    ))
}

fn handle_validate_network(req: &CoreRequest, started: Instant) -> anyhow::Result<CoreResponse> {
    let network_text = if let Some(text) = req.payload.get("network_text").and_then(Value::as_str) {
        text.to_string()
    } else if let Some(path) = req.payload.get("network_json_path").and_then(Value::as_str) {
        std::fs::read_to_string(path).context("read network.json")?
    } else {
        "{}".to_string()
    };
    let network = parse_network_text(&network_text).context("parse network.json")?;
    let names = collect_node_names(&network);
    let (errors, warnings) = validate_network(&network);
    Ok(CoreResponse::validation(
        req,
        json!({"node_count": names.len(), "write_allowed": errors.is_empty(), "apply_allowed": errors.is_empty()}),
        errors,
        warnings,
        started,
    ))
}

fn print_response(response: &CoreResponse) {
    match serde_json::to_string_pretty(response) {
        Ok(text) => println!("{text}"),
        Err(_) => println!("{{\"version\":\"1\",\"op\":\"unknown\",\"ok\":false,\"errors\":[{{\"code\":\"response_serialization_failed\",\"severity\":\"error\",\"message\":\"failed to serialize response\"}}]}}"),
    }
}
