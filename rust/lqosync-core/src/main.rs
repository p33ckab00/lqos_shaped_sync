use anyhow::Context;
use clap::Parser;
use lqosync_core::apply_manifest::build_apply_manifest_payload;
use lqosync_core::apply_transaction::execute_apply_transaction_payload;
use lqosync_core::authority_readiness::evaluate_authority_readiness_payload;
use lqosync_core::authority_pilot::{build_authority_pilot_plan_payload, evaluate_full_rust_readiness_payload};
use lqosync_core::atomic_state::{append_audit_jsonl_payload, atomic_write_json_state_payload, atomic_write_text_payload, validate_json_state_payload};
use lqosync_core::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use lqosync_core::circuits::normalize_circuits_payload;
use lqosync_core::collector_bundle::build_collector_circuit_bundle_payload;
use lqosync_core::collector_parity::compare_collector_bundle_parity_payload;
use lqosync_core::diff::{diff_files_payload, diff_network_text, diff_shaped_devices_text};
use lqosync_core::network::{collect_node_names, parse_network_text, validate_network};
use lqosync_core::policy::evaluate_policy_payload;
use lqosync_core::protocol::{CoreRequest, CoreResponse, PROTOCOL_VERSION};
use lqosync_core::rollback_executor::execute_rollback_payload;
use lqosync_core::routeros_plan::build_routeros_collector_plan_payload;
use lqosync_core::routeros_results::validate_routeros_read_results_payload;
use lqosync_core::routeros_transport::build_routeros_transport_session_payload;
use lqosync_core::routeros_live_pilot::build_routeros_live_read_pilot_payload;
use lqosync_core::routeros_read_pilot::run_routeros_read_pilot_payload;
use lqosync_core::routeros_api_codec::build_routeros_api_sentence_payload;
use lqosync_core::routeros_api_reply::decode_routeros_api_reply_payload;
use lqosync_core::routeros_api_frame::codec_routeros_api_frame_payload;
use lqosync_core::routeros_offline_session::run_routeros_offline_session_payload;
use lqosync_core::routeros_tcp_probe::run_routeros_tcp_connectivity_pilot_payload;
use lqosync_core::routeros_auth_plan::build_routeros_auth_plan_payload;
use lqosync_core::routeros_auth_handshake::run_routeros_auth_handshake_payload;
use lqosync_core::routeros_auth_session::build_routeros_auth_session_contract_payload;
use lqosync_core::routeros_authenticated_read::run_routeros_authenticated_read_fixture_payload;
use lqosync_core::routeros_live_read_adapter::run_routeros_live_read_adapter_pilot_payload;
use lqosync_core::collector_authority_pilot::evaluate_rust_collector_authority_pilot_payload;
use lqosync_core::collector_authority_manifest::build_collector_authority_manifest_payload;
use lqosync_core::collector_authority_selection::build_collector_authority_selection_payload;
use lqosync_core::collector_authority_dry_run::build_collector_authority_dry_run_bundle_payload;
use lqosync_core::collector_run_cycle_shadow::build_run_cycle_rust_shadow_report_payload;
use lqosync_core::self_test::{advertised_operations, self_test_payload};
use lqosync_core::shaped_devices::{parse_csv_text, render_csv_text, validate_rows};
use lqosync_core::sync_plan::evaluate_sync_plan_payload;
use lqosync_core::transaction_journal::{append_transaction_journal_payload, build_rollback_manifest_payload, build_transaction_journal_payload};
use lqosync_core::transaction_history::{build_rollback_from_journal_payload, read_transaction_journal_payload};
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
            "operations": advertised_operations()
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
        "build-routeros-collector-plan" => {
            let (result, errors, warnings) = build_routeros_collector_plan_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "validate-routeros-read-results" => {
            let (result, errors, warnings) = validate_routeros_read_results_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-routeros-transport-session" => {
            let (result, errors, warnings) = build_routeros_transport_session_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-routeros-live-read-pilot" => {
            let (result, errors, warnings) = build_routeros_live_read_pilot_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-read-pilot" => {
            let (result, errors, warnings) = run_routeros_read_pilot_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-routeros-api-sentence" => {
            let (result, errors, warnings) = build_routeros_api_sentence_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "decode-routeros-api-reply" => {
            let (result, errors, warnings) = decode_routeros_api_reply_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "codec-routeros-api-frame" => {
            let (result, errors, warnings) = codec_routeros_api_frame_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-offline-session" => {
            let (result, errors, warnings) = run_routeros_offline_session_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-tcp-connectivity-pilot" => {
            let (result, errors, warnings) = run_routeros_tcp_connectivity_pilot_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-routeros-auth-plan" => {
            let (result, errors, warnings) = build_routeros_auth_plan_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-auth-handshake" => {
            let (result, errors, warnings) = run_routeros_auth_handshake_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-routeros-auth-session-contract" => {
            let (result, errors, warnings) = build_routeros_auth_session_contract_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-authenticated-read-fixture" => {
            let (result, errors, warnings) = run_routeros_authenticated_read_fixture_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "run-routeros-live-read-adapter-pilot" => {
            let (result, errors, warnings) = run_routeros_live_read_adapter_pilot_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "evaluate-rust-collector-authority-pilot" => {
            let (result, errors, warnings) = evaluate_rust_collector_authority_pilot_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-collector-authority-manifest" => {
            let (result, errors, warnings) = build_collector_authority_manifest_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-collector-authority-selection" => {
            let (result, errors, warnings) = build_collector_authority_selection_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-collector-authority-dry-run-bundle" => {
            let (result, errors, warnings) = build_collector_authority_dry_run_bundle_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-run-cycle-rust-shadow-report" => {
            let (result, errors, warnings) = build_run_cycle_rust_shadow_report_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-collector-circuit-bundle" => {
            let (result, errors, warnings) = build_collector_circuit_bundle_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "compare-collector-bundle-parity" => {
            let (result, errors, warnings) = compare_collector_bundle_parity_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "evaluate-sync-plan" => {
            let (result, errors, warnings) = evaluate_sync_plan_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-apply-manifest" => {
            let (result, errors, warnings) = build_apply_manifest_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "execute-apply-transaction" => {
            let (result, errors, warnings) = execute_apply_transaction_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-transaction-journal" => {
            let (result, errors, warnings) = build_transaction_journal_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }

        "append-transaction-journal" => {
            let (result, errors, warnings) = append_transaction_journal_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "read-transaction-journal" => {
            let (result, errors, warnings) = read_transaction_journal_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-rollback-from-journal" => {
            let (result, errors, warnings) = build_rollback_from_journal_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-rollback-manifest" => {
            let (result, errors, warnings) = build_rollback_manifest_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "execute-rollback" => {
            let (result, errors, warnings) = execute_rollback_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "evaluate-authority-readiness" => {
            let (result, errors, warnings) = evaluate_authority_readiness_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "evaluate-full-rust-readiness" => {
            let (result, errors, warnings) = evaluate_full_rust_readiness_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "build-authority-pilot-plan" => {
            let (result, errors, warnings) = build_authority_pilot_plan_payload(&req.payload);
            Ok(CoreResponse::validation(req, result, errors, warnings, started))
        }
        "self-test" => {
            let (result, errors, warnings) = self_test_payload(&req.payload);
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
