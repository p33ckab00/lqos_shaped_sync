use crate::collector_authority_activation::build_collector_authority_activation_plan_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn number_value(v: Option<&Value>, default: u64) -> u64 {
    v.and_then(Value::as_u64).unwrap_or(default)
}

fn config_value<'a>(payload: &'a Value, key: &str) -> Option<&'a Value> {
    payload
        .get("rust_core")
        .and_then(|v| v.get(key))
        .or_else(|| payload.get("config").and_then(|c| c.get("rust_core")).and_then(|v| v.get(key)))
}

fn contract_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("capr-{}", &digest[..16])
}

/// Build a non-mutating Collector Authority Pilot runtime contract.
///
/// v4.1 is the bridge after the activation plan. It takes a clean activation
/// plan and creates a runtime contract for a future Rust collector authority
/// pilot. It still cannot switch production authority, drive cleanup, write
/// generated files, or apply LibreQoS output. Python remains the production
/// authority and fallback is mandatory.
pub fn build_collector_authority_runtime_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "contract"), "execute" | "promote" | "switch" | "authority" | "apply" | "production");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_runtime_execute_not_implemented",
            Some("collector_authority_runtime".to_string()),
            "This release only builds a collector authority runtime contract. It does not switch production collector authority away from Python.",
        ));
    }

    let allow_runtime = bool_value(config_value(payload, "allow_collector_authority_runtime_contract"), false);
    let runtime_pilot = bool_value(config_value(payload, "collector_authority_runtime_pilot"), false);
    let runtime_mode = str_value(config_value(payload, "collector_authority_runtime_mode"), "contract_only");
    let require_activation = bool_value(config_value(payload, "collector_authority_runtime_require_activation_plan"), true);
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_runtime_require_python_fallback"), true);
    let max_stale_seconds = number_value(config_value(payload, "collector_authority_runtime_max_shadow_age_seconds"), 900);
    let shadow_age_seconds = number_value(payload.get("shadow_age_seconds").or_else(|| config_value(payload, "collector_authority_shadow_age_seconds")), 0);

    let activation_value = payload
        .get("collector_authority_activation_plan")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_authority_activation_plan"))
        .cloned();

    let (activation_plan, activation_errors, mut activation_warnings) = match activation_value {
        Some(v) if v.is_object() => (v, Vec::new(), Vec::new()),
        _ => build_collector_authority_activation_plan_payload(payload),
    };
    warnings.append(&mut activation_warnings);

    if !activation_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_activation_not_clean",
            Some("collector_authority_activation_plan".to_string()),
            "Collector authority activation plan returned errors; runtime contract remains blocked.",
        ));
    }

    let activation_status = activation_plan.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let activation_ready = activation_errors.is_empty()
        && activation_status == "collector_authority_activation_ready_for_pilot"
        && activation_plan.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && activation_plan.get("python_collector_fallback_required").and_then(Value::as_bool) == Some(true);

    if require_activation && !activation_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_runtime_activation_not_ready",
            Some("collector_authority_activation_plan".to_string()),
            "Collector authority activation plan is not ready; runtime contract remains shadow-only.",
        ));
    }
    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_runtime_requires_python_fallback",
            Some("rust_core.collector_authority_runtime_require_python_fallback".to_string()),
            "Collector authority runtime pilot requires Python collector fallback to remain enabled in this release.",
        ));
    }
    if shadow_age_seconds > max_stale_seconds {
        warnings.push(Diagnostic::warning(
            "collector_authority_runtime_shadow_state_stale",
            Some("collector_authority_runtime.shadow_age_seconds".to_string()),
            "Rust-shadow collector state is older than the runtime pilot freshness limit.",
        ).with_value(json!({"shadow_age_seconds": shadow_age_seconds, "max_shadow_age_seconds": max_stale_seconds})));
    }

    let runtime_requested = allow_runtime && runtime_pilot && runtime_mode == "rust_collector_authority_runtime_contract";
    let shadow_fresh = shadow_age_seconds <= max_stale_seconds;
    let contract_ready = errors.is_empty()
        && runtime_requested
        && (!require_activation || activation_ready)
        && require_python_fallback
        && shadow_fresh;

    let status = if !errors.is_empty() {
        "blocked"
    } else if contract_ready {
        "collector_authority_runtime_contract_ready"
    } else if activation_ready {
        "collector_authority_runtime_waiting_for_gates"
    } else {
        "collector_authority_runtime_shadow_only"
    };

    let rust_row_count = activation_plan.get("rust_row_count").and_then(Value::as_u64).unwrap_or(0);
    let python_row_count = activation_plan.get("python_row_count").and_then(Value::as_u64).unwrap_or(0);
    let sources = payload.get("sources").cloned().unwrap_or_else(|| json!([]));

    let seed = json!({
        "status": status,
        "activation_status": activation_status,
        "runtime_mode": runtime_mode,
        "rust_row_count": rust_row_count,
        "shadow_age_seconds": shadow_age_seconds,
    });

    let result = json!({
        "mode": "collector_authority_runtime_contract",
        "status": status,
        "runtime_contract_id": contract_id(&seed),
        "collector_authority": "python_authoritative",
        "target_authority": if contract_ready { "rust_collector_authority_runtime_candidate" } else { "python_authoritative" },
        "runtime_requested": runtime_requested,
        "allow_runtime_contract": allow_runtime,
        "runtime_pilot": runtime_pilot,
        "runtime_mode": runtime_mode,
        "require_activation_plan": require_activation,
        "require_python_fallback": require_python_fallback,
        "activation_status": activation_status,
        "activation_ready": activation_ready,
        "shadow_age_seconds": shadow_age_seconds,
        "max_shadow_age_seconds": max_stale_seconds,
        "shadow_fresh": shadow_fresh,
        "sources": sources,
        "python_row_count": python_row_count,
        "rust_row_count": rust_row_count,
        "collector_authority_activation_plan": activation_plan,
        "full_rust_backend": false,
        "production_collector_authority_switched": false,
        "collector_authority_switch_supported": false,
        "python_collector_fallback_required": true,
        "runtime_contract_only": true,
        "rust_pilot_may_select_rows_for_diagnostics": contract_ready,
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
        "next_stage": "rust_collector_authority_pilot_controlled_handoff",
        "note": "v4.1 builds a non-mutating runtime contract for a future Rust collector authority pilot. It does not switch production authority away from Python."
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
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"runtime-contract-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
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

    fn enable_all_gates(payload: &mut Value) {
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("successful_shadow_cycles".to_string(), json!(3));
            obj.insert("shadow_age_seconds".to_string(), json!(30));
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
                "collector_authority_min_shadow_cycles": 3,
                "collector_authority_runtime_pilot": true,
                "allow_collector_authority_runtime_contract": true,
                "collector_authority_runtime_mode": "rust_collector_authority_runtime_contract",
                "collector_authority_runtime_require_activation_plan": true,
                "collector_authority_runtime_require_python_fallback": true,
                "collector_authority_runtime_max_shadow_age_seconds": 900
            }));
        }
    }

    #[test]
    fn defaults_to_shadow_only_runtime_contract() {
        let payload = base_payload();
        let (result, errors, _warnings) = build_collector_authority_runtime_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_runtime_shadow_only"));
        assert_eq!(result.get("collector_authority").and_then(Value::as_str), Some("python_authoritative"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn builds_ready_runtime_contract_when_activation_and_gates_are_ready() {
        let mut payload = base_payload();
        enable_all_gates(&mut payload);
        let (result, errors, _warnings) = build_collector_authority_runtime_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_runtime_contract_ready"));
        assert_eq!(result.get("runtime_contract_only").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("runtime-contract-password"));
        assert!(!text.contains("\"password\":"));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = base_payload();
        enable_all_gates(&mut payload);
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("execute".to_string(), json!(true));
        }
        let (result, errors, _warnings) = build_collector_authority_runtime_contract_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
