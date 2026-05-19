use anyhow::Context;
use clap::Parser;
use lqosync_core::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use lqosync_core::protocol::{CoreRequest, CoreResponse, PROTOCOL_VERSION};
use lqosync_core::diff::{diff_files_payload, diff_network_text, diff_shaped_devices_text};
use lqosync_core::network::{collect_node_names, parse_network_text, validate_network};
use lqosync_core::shaped_devices::{parse_csv_text, render_csv_text, validate_rows};
use lqosync_core::validators::{validate_collector_output_payload, validate_config_value, validate_files_payload};
use serde_json::{json, Value};
use std::io::{self, Read};
use std::time::Instant;

#[derive(Parser, Debug)]
#[command(name = "lqosync-core", version, about = "Rust safety core for LQoSync")]
struct Args {
    /// Read a JSON protocol request from stdin. This is the default behavior.
    #[arg(long, default_value_t = true)]
    json: bool,
}

fn main() {
    let started = Instant::now();
    let _args = Args::parse();
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        let response = CoreResponse::failure("unknown", None, "stdin_read_failed", format!("Failed to read stdin: {e}"), started);
        print_response(&response);
        std::process::exit(1);
    }

    let req: CoreRequest = match serde_json::from_str(&input) {
        Ok(req) => req,
        Err(e) => {
            let response = CoreResponse::failure("unknown", None, "invalid_request_json", format!("Invalid request JSON: {e}"), started);
            print_response(&response);
            std::process::exit(1);
        }
    };

    let response = match handle_request(&req, started) {
        Ok(response) => response,
        Err(e) => CoreResponse::failure(req.op.clone(), req.request_id.clone(), "operation_failed", e.to_string(), started),
    };
    let exit_code = if response.ok { 0 } else { 2 };
    print_response(&response);
    std::process::exit(exit_code);
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
