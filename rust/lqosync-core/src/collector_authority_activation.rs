use crate::collector_run_cycle_shadow::build_run_cycle_rust_shadow_report_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn number_value(v: Option<&Value>, default: u64) -> u64 {
    v.and_then(Value::as_u64).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn config_value<'a>(payload: &'a Value, key: &str) -> Option<&'a Value> {
    payload
        .get("rust_core")
        .and_then(|v| v.get(key))
        .or_else(|| payload.get("config").and_then(|c| c.get("rust_core")).and_then(|v| v.get(key)))
}

fn activation_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("cap-{}", &digest[..16])
}

/// Build a non-mutating Collector Authority Pilot activation plan.
///
/// v4.0 is the bridge between run_cycle Rust-shadow reporting and a future
/// production collector authority pilot. It is still a plan only: Python remains
/// authoritative, Rust cannot drive cleanup/apply, and no live RouterOS read is
/// executed by this operation.
pub fn build_collector_authority_activation_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "plan"), "execute" | "promote" | "switch" | "authority" | "apply" | "production");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_activation_execute_not_implemented",
            Some("collector_authority_activation".to_string()),
            "This release only builds a collector authority activation plan. It does not switch production collector authority away from Python.",
        ));
    }

    let allow_activation = bool_value(config_value(payload, "allow_collector_authority_activation"), false);
    let activation_pilot = bool_value(config_value(payload, "collector_authority_activation_pilot"), false);
    let activation_mode = str_value(config_value(payload, "collector_authority_activation_mode"), "shadow_only");
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_require_python_fallback"), true);
    let require_shadow_report = bool_value(config_value(payload, "collector_authority_require_run_cycle_shadow"), true);
    let min_shadow_cycles = number_value(config_value(payload, "collector_authority_min_shadow_cycles"), 3);
    let successful_shadow_cycles = number_value(
        payload.get("successful_shadow_cycles")
            .or_else(|| config_value(payload, "collector_authority_successful_shadow_cycles")),
        0,
    );

    let report_value = payload
        .get("run_cycle_rust_shadow_report")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("run_cycle_rust_shadow_report"))
        .cloned();

    let (run_cycle_report, report_errors, mut report_warnings) = match report_value {
        Some(v) if v.is_object() => (v, Vec::new(), Vec::new()),
        _ => build_run_cycle_rust_shadow_report_payload(payload),
    };
    warnings.append(&mut report_warnings);

    if !report_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "run_cycle_rust_shadow_report_not_clean",
            Some("run_cycle_rust_shadow_report".to_string()),
            "run_cycle Rust-shadow report returned errors; collector authority activation remains blocked.",
        ));
    }

    let report_status = run_cycle_report.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let rust_shadow_ready = report_errors.is_empty()
        && report_status == "run_cycle_rust_shadow_ready"
        && run_cycle_report.get("rust_shadow_ready").and_then(Value::as_bool).unwrap_or(false);
    let parity_verdict = run_cycle_report.get("parity_verdict").cloned().unwrap_or_else(|| json!("not_available"));
    let rust_row_count = run_cycle_report.get("rust_row_count").and_then(Value::as_u64).unwrap_or(0);
    let python_row_count = run_cycle_report.get("python_row_count").and_then(Value::as_u64).unwrap_or(0);
    let shadow_cycles_ok = successful_shadow_cycles >= min_shadow_cycles;
    let activation_requested = allow_activation && activation_pilot && activation_mode == "rust_collector_authority_pilot";

    if require_shadow_report && !rust_shadow_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_activation_shadow_not_ready",
            Some("run_cycle_rust_shadow_report".to_string()),
            "run_cycle Rust-shadow report is not ready; collector authority activation remains shadow-only.",
        ));
    }
    if !shadow_cycles_ok {
        warnings.push(Diagnostic::warning(
            "collector_authority_activation_shadow_cycles_insufficient",
            Some("collector_authority_activation.successful_shadow_cycles".to_string()),
            "Not enough successful Rust-shadow cycles have been recorded for collector authority activation.",
        ).with_value(json!({"successful_shadow_cycles": successful_shadow_cycles, "required_shadow_cycles": min_shadow_cycles})));
    }
    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_activation_requires_python_fallback",
            Some("rust_core.collector_authority_require_python_fallback".to_string()),
            "Collector authority pilot requires Python collector fallback to remain enabled in this release.",
        ));
    }

    let ready_for_pilot = errors.is_empty()
        && activation_requested
        && (!require_shadow_report || rust_shadow_ready)
        && shadow_cycles_ok
        && require_python_fallback;

    let status = if !errors.is_empty() {
        "blocked"
    } else if ready_for_pilot {
        "collector_authority_activation_ready_for_pilot"
    } else if rust_shadow_ready {
        "collector_authority_activation_waiting_for_gates_or_cycles"
    } else {
        "collector_authority_activation_shadow_only"
    };

    let seed = json!({
        "status": status,
        "report_status": report_status,
        "rust_row_count": rust_row_count,
        "successful_shadow_cycles": successful_shadow_cycles,
        "activation_mode": activation_mode,
    });

    let result = json!({
        "mode": "collector_authority_activation_plan",
        "status": status,
        "activation_plan_id": activation_id(&seed),
        "collector_authority": "python_authoritative",
        "target_authority": if ready_for_pilot { "rust_collector_authority_pilot_candidate" } else { "python_authoritative" },
        "activation_requested": activation_requested,
        "allow_activation": allow_activation,
        "activation_pilot": activation_pilot,
        "activation_mode": activation_mode,
        "require_python_fallback": require_python_fallback,
        "require_run_cycle_shadow": require_shadow_report,
        "required_shadow_cycles": min_shadow_cycles,
        "successful_shadow_cycles": successful_shadow_cycles,
        "shadow_cycles_ok": shadow_cycles_ok,
        "run_cycle_shadow_status": report_status,
        "rust_shadow_ready": rust_shadow_ready,
        "python_row_count": python_row_count,
        "rust_row_count": rust_row_count,
        "parity_verdict": parity_verdict,
        "run_cycle_rust_shadow_report": run_cycle_report,
        "full_rust_backend": false,
        "production_collector_authority_switched": false,
        "collector_authority_switch_supported": false,
        "python_collector_fallback_required": true,
        "rust_can_drive_cleanup": false,
        "rust_can_drive_apply": false,
        "rust_can_write_generated_files": false,
        "safe_for_cleanup": false,
        "write_allowed": false,
        "apply_allowed": false,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "next_stage": "rust_collector_authority_pilot_runtime_decision",
        "note": "v4.0 builds an auditable activation plan for a future Rust collector authority pilot. It does not switch production authority away from Python."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn base_payload() -> Value {
        let row = json!({"Circuit ID":"selftest", "Circuit Name":"selftest", "Device ID":"selftest", "Device Name":"selftest", "Parent Node":"15M-RB5009", "MAC":"AA:BB:CC:DD:EE:FF", "IPv4":"10.0.0.2", "IPv6":"", "Download Min Mbps":"7.5", "Upload Min Mbps":"7.5", "Download Max Mbps":"15", "Upload Max Mbps":"15", "Comment":"PPP"});
        json!({
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"activation-plan-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
            "sources": ["pppoe"],
            "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
            "python_rows": [row],
            "pppoe": {
                "active": [{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
                "secrets": [{"name":"selftest", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
                "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
            }
        })
    }

    fn enable_shadow_and_activation(payload: &mut Value) {
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("successful_shadow_cycles".to_string(), json!(3));
            obj.insert("rust_core".to_string(), json!({
                "allow_rust_collector_authority": true,
                "rust_collector_authority_pilot": true,
                "allow_rust_routeros_live_read_adapter": true,
                "routeros_live_read_adapter_pilot": true,
                "rust_collector_authority_sources": ["pppoe"],
                "collector_authority_mode": "rust_collector_authority_pilot",
                "collector_authority_manifest_pilot": true,
                "allow_collector_authority_manifest": true,
                "collector_authority_dry_run_selection_pilot": true,
                "allow_collector_authority_dry_run_selection": true,
                "collector_authority_dry_run_bundle_pilot": true,
                "allow_collector_authority_dry_run_bundle": true,
                "run_cycle_rust_shadow_report_enabled": true,
                "run_cycle_rust_shadow_report_pilot": true,
                "collector_authority_activation_pilot": true,
                "allow_collector_authority_activation": true,
                "collector_authority_activation_mode": "rust_collector_authority_pilot",
                "collector_authority_require_python_fallback": true,
                "collector_authority_require_run_cycle_shadow": true,
                "collector_authority_min_shadow_cycles": 3
            }));
        }
    }

    #[test]
    fn defaults_to_shadow_only_activation_plan() {
        let payload = base_payload();
        let (result, errors, _warnings) = build_collector_authority_activation_plan_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_activation_shadow_only"));
        assert_eq!(result.get("collector_authority").and_then(Value::as_str), Some("python_authoritative"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn becomes_ready_when_shadow_cycles_and_gates_are_ready() {
        let mut payload = base_payload();
        enable_shadow_and_activation(&mut payload);
        let (result, errors, _warnings) = build_collector_authority_activation_plan_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_activation_ready_for_pilot"));
        assert_eq!(result.get("shadow_cycles_ok").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("activation-plan-password"));
        assert!(!text.contains("\"password\":"));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = base_payload();
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("execute".to_string(), json!(true));
        }
        let (result, errors, _warnings) = build_collector_authority_activation_plan_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
