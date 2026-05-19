use crate::protocol::Diagnostic;
use crate::routeros_live_pilot::build_routeros_live_read_pilot_payload;
use crate::routeros_results::validate_routeros_read_results_payload;
use serde_json::{json, Value};

fn as_bool(value: Option<&Value>, default: bool) -> bool {
    value.and_then(Value::as_bool).unwrap_or(default)
}

fn as_f64(value: Option<&Value>, default: f64) -> f64 {
    value.and_then(Value::as_f64).unwrap_or(default)
}

fn as_str<'a>(value: Option<&'a Value>, default: &'a str) -> &'a str {
    value.and_then(Value::as_str).unwrap_or(default)
}

fn as_rows(value: Option<&Value>) -> Vec<Value> {
    match value {
        Some(Value::Array(rows)) => rows.clone(),
        _ => Vec::new(),
    }
}

fn public_plan_from_selected(selected: &Value) -> Value {
    let mut commands = Vec::new();
    if selected.is_object() && !selected.is_null() {
        commands.push(selected.clone());
    }
    json!({
        "mode": "fixture_selected_command_plan",
        "authority": "none",
        "status": if commands.is_empty() { "empty" } else { "ready" },
        "command_count": commands.len(),
        "required_command_count": commands.iter().filter(|c| c.get("required").and_then(Value::as_bool).unwrap_or(false)).count(),
        "commands": commands,
        "full_rust_backend": false,
        "note": "This minimal plan is built from a selected RouterOS live-read pilot command for fixture validation only."
    })
}

/// Execute a RouterOS read pilot against a fixture adapter.
///
/// This is the first executable adapter shape, but it is intentionally offline in
/// v2.4. It accepts fixture rows for a selected command, validates them using the
/// RouterOS read-result contract, and returns a trusted/blocked result without
/// opening sockets, consuming credentials, or replacing Python collectors.
pub fn run_routeros_read_pilot_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let adapter = as_str(payload.get("adapter"), "fixture");
    let execute = as_bool(payload.get("execute"), false);
    let mode = as_str(payload.get("mode"), "rehearsal");
    let fixture_rows = as_rows(payload.get("fixture_rows").or_else(|| payload.get("rows")));
    let fixture_status = as_str(payload.get("fixture_status"), "ok");
    let duration_ms = as_f64(payload.get("duration_ms"), 0.0);

    let pilot_payload = json!({
        "config": payload.get("config").cloned().unwrap_or_else(|| json!({})),
        "router": payload.get("router").cloned().unwrap_or_else(|| json!("")),
        "source": payload.get("source").cloned().unwrap_or_else(|| json!("")),
        "path": payload.get("path").cloned().unwrap_or_else(|| json!("")),
        "mode": "rehearsal",
        "execute": false
    });
    let (pilot, pilot_errors, pilot_warnings) = build_routeros_live_read_pilot_payload(&pilot_payload);
    errors.extend(pilot_errors);
    warnings.extend(pilot_warnings);

    if adapter != "fixture" {
        errors.push(Diagnostic::error(
            "routeros_live_adapter_not_implemented",
            Some("adapter".to_string()),
            "Only the offline fixture adapter is implemented in this release. Live RouterOS sockets are still disabled.",
        ));
    }
    if mode == "live" || (execute && adapter != "fixture") {
        errors.push(Diagnostic::error(
            "routeros_live_socket_transport_disabled",
            Some("mode".to_string()),
            "Live RouterOS socket transport is not implemented in v2.4. Use adapter=fixture for an offline execution rehearsal.",
        ));
    }

    let selected = pilot.get("selected_command").cloned().unwrap_or(Value::Null);
    if selected.is_null() {
        errors.push(Diagnostic::error(
            "routeros_read_pilot_no_selected_command",
            Some("selected_command".to_string()),
            "No selected RouterOS command was available for the read pilot fixture.",
        ));
    }

    let router = selected.get("router").and_then(Value::as_str).unwrap_or("unknown");
    let source = selected.get("source").and_then(Value::as_str).unwrap_or("unknown");
    let path = selected.get("path").and_then(Value::as_str).unwrap_or("");
    let read_result = json!({
        "router": router,
        "source": source,
        "path": path,
        "status": fixture_status,
        "rows": fixture_rows,
        "duration_ms": duration_ms,
        "adapter": "fixture",
        "connection_attempted": false,
        "credential_material": "none"
    });

    let plan = public_plan_from_selected(&selected);
    let validation_payload = json!({
        "plan": plan,
        "results": [read_result.clone()],
        "previous_counts": payload.get("previous_counts").cloned().unwrap_or_else(|| json!({})),
        "slow_ms_threshold": payload.get("slow_ms_threshold").cloned().unwrap_or_else(|| json!(2000.0)),
        "strict": payload.get("strict").cloned().unwrap_or_else(|| json!(false))
    });
    let (validation, validation_errors, validation_warnings) = validate_routeros_read_results_payload(&validation_payload);
    errors.extend(validation_errors);
    warnings.extend(validation_warnings);

    let status = if !errors.is_empty() {
        "blocked"
    } else if execute {
        "fixture_executed"
    } else {
        "fixture_rehearsal"
    };

    let result = json!({
        "mode": "routeros_read_pilot_fixture",
        "status": status,
        "adapter": adapter,
        "execute_requested": execute,
        "executed": execute && adapter == "fixture" && errors.is_empty(),
        "connection_attempt_count": 0,
        "live_transport_supported": false,
        "full_rust_backend": false,
        "selected_command": selected,
        "read_result": read_result,
        "read_validation": validation,
        "row_count": read_result.get("rows").and_then(Value::as_array).map(|r| r.len()).unwrap_or(0),
        "safe_for_cleanup": errors.is_empty() && validation.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(false),
        "credential_material": "redacted_or_absent",
        "next_stage": "rust_routeros_socket_transport_adapter",
        "note": "v2.4 executes only the offline fixture adapter. No RouterOS sockets are opened and Python collectors remain authoritative."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn executes_fixture_read_without_network() {
        let payload = json!({
            "execute": true,
            "adapter": "fixture",
            "router": "R1",
            "source": "pppoe",
            "path": "/ppp/active",
            "fixture_rows": [{"name":"user1", "address":"10.0.0.2"}],
            "config": {"routers":[{"name":"R1", "enabled":true, "address":"10.0.0.1", "username":"admin", "password":"super_private_pw_123", "pppoe":{"enabled":true}}]}
        });
        let (result, errors, _warnings) = run_routeros_read_pilot_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("fixture_executed"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("row_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("safe_for_cleanup").and_then(Value::as_bool), Some(true));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super_private_pw_123"));
        assert!(!text.contains("\\\"password\\\""));
    }

    #[test]
    fn blocks_live_adapter() {
        let payload = json!({
            "execute": true,
            "adapter": "live",
            "mode": "live",
            "router": "R1",
            "source": "pppoe",
            "config": {"routers":[{"name":"R1", "enabled":true, "address":"10.0.0.1", "username":"admin", "password":"secret", "pppoe":{"enabled":true}}]}
        });
        let (result, errors, _warnings) = run_routeros_read_pilot_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }
}
