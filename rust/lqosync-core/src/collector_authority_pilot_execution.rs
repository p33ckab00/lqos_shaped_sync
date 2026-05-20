use crate::collector_authority_switch::build_collector_authority_switch_rehearsal_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
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

fn pilot_execution_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("cape-{}", &digest[..16])
}

/// Build a non-mutating collector-authority pilot execution contract.
///
/// v4.3 is the bridge after the switch rehearsal. It proves that the system
/// has an auditable contract for a future Rust collector authority pilot run,
/// while still refusing to switch production collector authority, drive
/// cleanup, write generated files, or apply LibreQoS in this release.
pub fn build_collector_authority_pilot_execution_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "contract"), "execute" | "switch" | "promote" | "authority" | "apply" | "production");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_pilot_execution_not_implemented",
            Some("collector_authority_pilot_execution".to_string()),
            "This release only builds a collector authority pilot execution contract. It does not execute a production collector authority switch.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_collector_authority_pilot_execution_contract"), false);
    let pilot_enabled = bool_value(config_value(payload, "collector_authority_pilot_execution_pilot"), false);
    let execution_mode = str_value(config_value(payload, "collector_authority_pilot_execution_mode"), "contract_only");
    let require_switch_rehearsal = bool_value(config_value(payload, "collector_authority_pilot_execution_require_switch_rehearsal"), true);
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_pilot_execution_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "collector_authority_pilot_execution_require_manual_confirmation"), true);
    let max_shadow_age = config_value(payload, "collector_authority_pilot_execution_max_shadow_age_seconds")
        .and_then(Value::as_u64)
        .unwrap_or(900);
    let shadow_age = payload.get("shadow_age_seconds").and_then(Value::as_u64).unwrap_or(0);
    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == "CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION";

    let switch_value = payload
        .get("collector_authority_switch_rehearsal")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_authority_switch_rehearsal"))
        .cloned();

    let (switch_rehearsal, switch_errors, mut switch_warnings) = match switch_value {
        Some(v) if v.is_object() => (v, Vec::new(), Vec::new()),
        _ => build_collector_authority_switch_rehearsal_payload(payload),
    };
    warnings.append(&mut switch_warnings);

    if !switch_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_execution_switch_not_clean",
            Some("collector_authority_switch_rehearsal".to_string()),
            "Collector authority switch rehearsal returned errors; pilot execution contract remains blocked.",
        ));
    }

    let switch_status = switch_rehearsal.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let switch_ready = switch_errors.is_empty()
        && switch_status == "collector_authority_switch_rehearsal_ready"
        && switch_rehearsal.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && switch_rehearsal.get("collector_authority_switch_executed").and_then(Value::as_bool) == Some(false)
        && switch_rehearsal.get("python_collector_fallback_required").and_then(Value::as_bool) == Some(true);

    if require_switch_rehearsal && !switch_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_execution_switch_not_ready",
            Some("collector_authority_switch_rehearsal".to_string()),
            "Collector authority switch rehearsal is not ready; pilot execution contract remains shadow-only.",
        ));
    }
    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_pilot_execution_requires_python_fallback",
            Some("rust_core.collector_authority_pilot_execution_require_python_fallback".to_string()),
            "Collector authority pilot execution contract requires Python collector fallback in this release.",
        ));
    }
    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_execution_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow collector output is older than the configured maximum age; pilot execution contract remains waiting.",
        ));
    }
    if !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_execution_confirmation_missing",
            Some("collector_authority_pilot_execution.confirmation".to_string()),
            "Manual confirmation token is missing; pilot execution contract remains waiting for confirmation.",
        ));
    }

    let requested = allow_contract && pilot_enabled && execution_mode == "rust_collector_authority_pilot_execution_contract";
    let ready = errors.is_empty()
        && requested
        && (!require_switch_rehearsal || switch_ready)
        && require_python_fallback
        && confirmation_ok
        && shadow_age <= max_shadow_age;

    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "collector_authority_pilot_execution_contract_ready"
    } else if switch_ready {
        "collector_authority_pilot_execution_waiting_for_gates"
    } else {
        "collector_authority_pilot_execution_shadow_only"
    };

    let rust_row_count = switch_rehearsal.get("rust_row_count").and_then(Value::as_u64).unwrap_or(0);
    let python_row_count = switch_rehearsal.get("python_row_count").and_then(Value::as_u64).unwrap_or(0);
    let sources = payload.get("sources").cloned().unwrap_or_else(|| json!([]));

    let seed = json!({
        "status": status,
        "switch_status": switch_status,
        "execution_mode": execution_mode,
        "rust_row_count": rust_row_count,
        "confirmation_ok": confirmation_ok,
        "shadow_age_seconds": shadow_age,
    });

    let result = json!({
        "mode": "collector_authority_pilot_execution_contract",
        "status": status,
        "pilot_execution_contract_id": pilot_execution_id(&seed),
        "collector_authority": "python_authoritative",
        "target_authority": if ready { "rust_collector_authority_pilot_candidate" } else { "python_authoritative" },
        "contract_requested": requested,
        "allow_pilot_execution_contract": allow_contract,
        "pilot_execution_pilot": pilot_enabled,
        "pilot_execution_mode": execution_mode,
        "require_switch_rehearsal": require_switch_rehearsal,
        "require_python_fallback": require_python_fallback,
        "require_manual_confirmation": require_manual_confirmation,
        "manual_confirmation_ok": confirmation_ok,
        "max_shadow_age_seconds": max_shadow_age,
        "shadow_age_seconds": shadow_age,
        "switch_status": switch_status,
        "switch_ready": switch_ready,
        "sources": sources,
        "python_row_count": python_row_count,
        "rust_row_count": rust_row_count,
        "collector_authority_switch_rehearsal": switch_rehearsal,
        "full_rust_backend": false,
        "production_collector_authority_switched": false,
        "collector_authority_switch_supported": false,
        "collector_authority_switch_executed": false,
        "collector_authority_pilot_execution_supported": false,
        "collector_authority_pilot_execution_executed": false,
        "python_collector_fallback_required": true,
        "pilot_execution_contract_only": true,
        "rust_pilot_may_be_observed": ready,
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
        "next_stage": "rust_collector_authority_pilot_observation_window",
        "note": "v4.3 builds a non-mutating collector authority pilot execution contract after the switch rehearsal. It does not execute production authority transfer."
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
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"pilot-execution-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
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
            obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION"));
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
                "collector_authority_runtime_max_shadow_age_seconds": 900,
                "collector_authority_switch_rehearsal_pilot": true,
                "allow_collector_authority_switch_rehearsal": true,
                "collector_authority_switch_mode": "rust_collector_authority_switch_rehearsal",
                "collector_authority_switch_require_runtime_contract": true,
                "collector_authority_switch_require_python_fallback": true,
                "collector_authority_switch_require_manual_confirmation": true,
                "collector_authority_pilot_execution_pilot": true,
                "allow_collector_authority_pilot_execution_contract": true,
                "collector_authority_pilot_execution_mode": "rust_collector_authority_pilot_execution_contract",
                "collector_authority_pilot_execution_require_switch_rehearsal": true,
                "collector_authority_pilot_execution_require_python_fallback": true,
                "collector_authority_pilot_execution_require_manual_confirmation": true,
                "collector_authority_pilot_execution_max_shadow_age_seconds": 900
            }));
        }
    }

    #[test]
    fn defaults_to_shadow_only_pilot_execution_contract() {
        let payload = base_payload();
        let (result, errors, _warnings) = build_collector_authority_pilot_execution_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_pilot_execution_shadow_only"));
        assert_eq!(result.get("collector_authority").and_then(Value::as_str), Some("python_authoritative"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn builds_ready_pilot_execution_contract_when_switch_and_gates_are_ready() {
        let mut payload = base_payload();
        enable_all_gates(&mut payload);
        let (result, errors, _warnings) = build_collector_authority_pilot_execution_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_pilot_execution_contract_ready"));
        assert_eq!(result.get("pilot_execution_contract_only").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("collector_authority_pilot_execution_executed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("pilot-execution-password"));
        assert!(!text.contains("\"password\":"));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = base_payload();
        enable_all_gates(&mut payload);
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("execute".to_string(), json!(true));
        }
        let (result, errors, _warnings) = build_collector_authority_pilot_execution_contract_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
