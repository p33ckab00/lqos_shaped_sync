use crate::collector_authority_pilot_execution::build_collector_authority_pilot_execution_contract_payload;
use crate::collector_parity::compare_collector_bundle_parity_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Map, Value};
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

fn number_value(v: Option<&Value>, default: u64) -> u64 {
    v.and_then(Value::as_u64).unwrap_or(default)
}

fn rows_from_value(value: Option<&Value>) -> Vec<Value> {
    match value {
        Some(Value::Array(items)) => items.iter().filter(|v| v.is_object()).cloned().collect(),
        Some(Value::Object(obj)) => obj.values().filter(|v| v.is_object()).cloned().collect(),
        _ => Vec::new(),
    }
}

fn result_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("capr-{}", &digest[..16])
}

fn first_object<'a>(payload: &'a Value, keys: &[&str]) -> Option<&'a Value> {
    for key in keys {
        if let Some(value) = payload.get(*key) {
            if let Some(result) = value.get("result") {
                if result.is_object() {
                    return Some(result);
                }
            }
            if value.is_object() {
                return Some(value);
            }
        }
    }
    None
}

/// Evaluate the result of a future Rust collector authority pilot without enabling authority.
///
/// v4.4 is still a non-mutating bridge. It reads the pilot execution contract
/// plus observed pilot metrics/rows and reports whether the pilot result would
/// be accepted, reviewed, or blocked. Python collectors remain authoritative and
/// Rust still cannot drive cleanup/apply/write decisions in this release.
pub fn evaluate_collector_authority_pilot_result_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "evaluate"), "execute" | "switch" | "promote" | "authority" | "apply" | "production");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_pilot_result_execute_not_implemented",
            Some("collector_authority_pilot_result".to_string()),
            "This release only evaluates a collector authority pilot result. It does not switch production collector authority, drive cleanup, or apply LibreQoS.",
        ));
    }

    let allow_evaluation = bool_value(config_value(payload, "allow_collector_authority_pilot_result_evaluation"), false);
    let evaluator_pilot = bool_value(config_value(payload, "collector_authority_pilot_result_evaluator_pilot"), false);
    let evaluator_mode = str_value(config_value(payload, "collector_authority_pilot_result_mode"), "evaluate_only");
    let require_execution_contract = bool_value(config_value(payload, "collector_authority_pilot_result_require_execution_contract"), true);
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_pilot_result_require_python_fallback"), true);
    let require_no_cleanup_apply = bool_value(config_value(payload, "collector_authority_pilot_result_require_no_cleanup_apply"), true);
    let require_parity = bool_value(config_value(payload, "collector_authority_pilot_result_require_parity"), true);
    let max_shadow_age = number_value(config_value(payload, "collector_authority_pilot_result_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let execution_contract_value = first_object(payload, &[
        "collector_authority_pilot_execution_contract",
        "pilot_execution_contract",
        "collector_authority_pilot_execution",
    ])
    .cloned();

    let (execution_contract, execution_errors, mut execution_warnings) = match execution_contract_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => build_collector_authority_pilot_execution_contract_payload(payload),
    };
    warnings.append(&mut execution_warnings);

    if !execution_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_result_execution_contract_not_clean",
            Some("collector_authority_pilot_execution_contract".to_string()),
            "Collector authority pilot execution contract returned errors; pilot result evaluation remains shadow-only.",
        ));
    }

    let execution_status = execution_contract.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let execution_contract_ready = execution_errors.is_empty()
        && execution_status == "collector_authority_pilot_execution_contract_ready"
        && execution_contract.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && execution_contract.get("collector_authority_pilot_execution_executed").and_then(Value::as_bool) == Some(false)
        && execution_contract.get("python_collector_fallback_required").and_then(Value::as_bool) == Some(true);

    if require_execution_contract && !execution_contract_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_result_execution_contract_not_ready",
            Some("collector_authority_pilot_execution_contract".to_string()),
            "Collector authority pilot execution contract is not ready; pilot result evaluation remains shadow-only.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_pilot_result_requires_python_fallback",
            Some("rust_core.collector_authority_pilot_result_require_python_fallback".to_string()),
            "Collector authority pilot result evaluation requires Python collector fallback in this release.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_result_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow collector result is older than the configured maximum age; pilot result remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let observed = first_object(payload, &["collector_authority_pilot_result", "pilot_result", "pilot_observation"])
        .cloned()
        .unwrap_or_else(|| json!({}));

    let cleanup_attempted = bool_value(observed.get("cleanup_attempted").or_else(|| payload.get("cleanup_attempted")), false);
    let apply_attempted = bool_value(observed.get("apply_attempted").or_else(|| payload.get("apply_attempted")), false);
    let write_attempted = bool_value(observed.get("write_attempted").or_else(|| payload.get("write_attempted")), false);
    let authority_switched = bool_value(observed.get("production_collector_authority_switched").or_else(|| payload.get("production_collector_authority_switched")), false);
    let side_effect_free = !cleanup_attempted && !apply_attempted && !write_attempted && !authority_switched;

    if require_no_cleanup_apply && !side_effect_free {
        errors.push(Diagnostic::error(
            "collector_authority_pilot_result_side_effect_detected",
            Some("collector_authority_pilot_result".to_string()),
            "Collector authority pilot result indicates cleanup/apply/write/authority side effects, which are forbidden in this release.",
        ));
    }

    let rust_rows = rows_from_value(observed.get("rust_rows"))
        .into_iter()
        .chain(rows_from_value(payload.get("rust_rows")))
        .collect::<Vec<_>>();
    let python_rows = rows_from_value(observed.get("python_rows"))
        .into_iter()
        .chain(rows_from_value(payload.get("python_rows")))
        .collect::<Vec<_>>();

    let mut parity_result = payload
        .get("collector_parity")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_parity"))
        .cloned()
        .unwrap_or_else(|| json!({"verdict":"not_available","parity_score":0.0}));
    let mut parity_errors: Vec<Diagnostic> = Vec::new();
    if !python_rows.is_empty() || !rust_rows.is_empty() {
        let (computed_parity, p_errors, mut p_warnings) = compare_collector_bundle_parity_payload(&json!({
            "python_rows": python_rows,
            "rust_rows": rust_rows,
            "strict": false
        }));
        parity_result = computed_parity;
        parity_errors = p_errors;
        warnings.append(&mut p_warnings);
    }

    let parity_verdict = parity_result.get("verdict").and_then(Value::as_str).unwrap_or("not_available");
    let parity_pass = parity_errors.is_empty() && parity_verdict == "parity_pass";
    if require_parity && !parity_pass {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_result_parity_not_passed",
            Some("collector_parity".to_string()),
            "Collector authority pilot result parity has not passed; result remains under review.",
        ));
    }

    let observed_status = observed.get("status").and_then(Value::as_str).unwrap_or("pilot_result_not_supplied");
    let observed_errors = number_value(observed.get("error_count"), 0)
        + number_value(payload.get("pilot_error_count"), 0);
    let observed_ok = observed_errors == 0
        && matches!(observed_status,
            "pilot_shadow_complete" |
            "pilot_result_pass" |
            "collector_authority_pilot_result_pass" |
            "pilot_completed" |
            "ok" |
            "pilot_result_not_supplied");

    if observed_errors > 0 || !observed_ok {
        warnings.push(Diagnostic::warning(
            "collector_authority_pilot_result_observation_not_clean",
            Some("collector_authority_pilot_result".to_string()),
            "Collector authority pilot observation is not clean; result remains under review.",
        ).with_value(json!({"observed_status": observed_status, "observed_error_count": observed_errors})));
    }

    let requested = allow_evaluation && evaluator_pilot && evaluator_mode == "rust_collector_authority_pilot_result_evaluation";
    let shadow_fresh = shadow_age <= max_shadow_age;
    let pass = errors.is_empty()
        && requested
        && (!require_execution_contract || execution_contract_ready)
        && require_python_fallback
        && (!require_parity || parity_pass)
        && side_effect_free
        && observed_ok
        && shadow_fresh;

    let status = if !errors.is_empty() {
        "blocked"
    } else if pass {
        "collector_authority_pilot_result_pass"
    } else if execution_contract_ready {
        "collector_authority_pilot_result_review"
    } else {
        "collector_authority_pilot_result_shadow_only"
    };

    let seed = json!({
        "status": status,
        "execution_status": execution_status,
        "parity_verdict": parity_verdict,
        "observed_status": observed_status,
        "shadow_age_seconds": shadow_age,
    });

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("collector_authority_pilot_result_evaluation"));
    map.insert("status".to_string(), json!(status));
    map.insert("pilot_result_evaluation_id".to_string(), json!(result_id(&seed)));
    map.insert("collector_authority".to_string(), json!("python_authoritative"));
    map.insert("target_authority".to_string(), json!(if pass { "rust_collector_authority_pilot_candidate_validated" } else { "python_authoritative" }));
    map.insert("evaluation_requested".to_string(), json!(requested));
    map.insert("allow_pilot_result_evaluation".to_string(), json!(allow_evaluation));
    map.insert("pilot_result_evaluator_pilot".to_string(), json!(evaluator_pilot));
    map.insert("pilot_result_mode".to_string(), json!(evaluator_mode));
    map.insert("execution_contract_status".to_string(), json!(execution_status));
    map.insert("execution_contract_ready".to_string(), json!(execution_contract_ready));
    map.insert("collector_authority_pilot_execution_contract".to_string(), execution_contract);
    map.insert("observed_status".to_string(), json!(observed_status));
    map.insert("observed_error_count".to_string(), json!(observed_errors));
    map.insert("cleanup_attempted".to_string(), json!(cleanup_attempted));
    map.insert("apply_attempted".to_string(), json!(apply_attempted));
    map.insert("write_attempted".to_string(), json!(write_attempted));
    map.insert("side_effect_free".to_string(), json!(side_effect_free));
    map.insert("parity".to_string(), parity_result);
    map.insert("parity_pass".to_string(), json!(parity_pass));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("shadow_fresh".to_string(), json!(shadow_fresh));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("production_collector_authority_switched".to_string(), json!(false));
    map.insert("collector_authority_switch_executed".to_string(), json!(false));
    map.insert("collector_authority_pilot_result_evaluated".to_string(), json!(pass));
    map.insert("python_collector_fallback_required".to_string(), json!(true));
    map.insert("rust_can_drive_cleanup".to_string(), json!(false));
    map.insert("rust_can_drive_apply".to_string(), json!(false));
    map.insert("rust_can_write_generated_files".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("connection_attempt_count".to_string(), json!(0));
    map.insert("authentication_attempt_count".to_string(), json!(0));
    map.insert("api_sentence_write_count".to_string(), json!(0));
    map.insert("api_reply_read_count".to_string(), json!(0));
    map.insert("next_stage".to_string(), json!("rust_collector_authority_pilot_handoff_manifest"));
    map.insert("note".to_string(), json!("v4.4 evaluates a future Rust collector authority pilot result while keeping Python collectors authoritative and forbidding cleanup/apply/write authority."));

    for err in parity_errors {
        warnings.push(Diagnostic::warning(err.code, err.path, err.message));
    }

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn row() -> Value {
        json!({"Circuit ID":"selftest", "Circuit Name":"selftest", "Device ID":"selftest", "Device Name":"selftest", "Parent Node":"15M-RB5009", "MAC":"AA:BB:CC:DD:EE:FF", "IPv4":"10.0.0.2", "IPv6":"", "Download Min Mbps":"7.5", "Upload Min Mbps":"7.5", "Download Max Mbps":"15", "Upload Max Mbps":"15", "Comment":"PPP"})
    }

    fn base_payload() -> Value {
        json!({
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"pilot-result-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
            "sources": ["pppoe"],
            "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
            "python_rows": [row()],
            "rust_rows": [row()],
            "shadow_age_seconds": 30,
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
            obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION"));
            obj.insert("collector_authority_switch_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"));
            obj.insert("pilot_result".to_string(), json!({
                "status":"pilot_shadow_complete",
                "rust_rows":[row()],
                "python_rows":[row()],
                "cleanup_attempted":false,
                "apply_attempted":false,
                "write_attempted":false,
                "error_count":0
            }));
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
                "collector_authority_pilot_execution_max_shadow_age_seconds": 900,
                "collector_authority_pilot_result_evaluator_pilot": true,
                "allow_collector_authority_pilot_result_evaluation": true,
                "collector_authority_pilot_result_mode": "rust_collector_authority_pilot_result_evaluation",
                "collector_authority_pilot_result_require_execution_contract": true,
                "collector_authority_pilot_result_require_python_fallback": true,
                "collector_authority_pilot_result_require_no_cleanup_apply": true,
                "collector_authority_pilot_result_require_parity": true,
                "collector_authority_pilot_result_max_shadow_age_seconds": 900
            }));
        }
    }

    #[test]
    fn defaults_to_shadow_only_result_evaluation() {
        let payload = base_payload();
        let (result, errors, _warnings) = evaluate_collector_authority_pilot_result_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_pilot_result_shadow_only"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = base_payload();
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("execute".to_string(), json!(true));
        }
        let (result, errors, _warnings) = evaluate_collector_authority_pilot_result_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn evaluates_clean_pilot_result_as_pass_without_switching_authority() {
        let mut payload = base_payload();
        enable_all_gates(&mut payload);
        let (result, errors, _warnings) = evaluate_collector_authority_pilot_result_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_pilot_result_pass"));
        assert_eq!(result.get("collector_authority_pilot_result_evaluated").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("pilot-result-password"));
    }
}
