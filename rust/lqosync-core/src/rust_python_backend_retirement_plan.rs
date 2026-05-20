use crate::protocol::Diagnostic;
use crate::rust_full_backend_cutover_execution::build_full_rust_backend_cutover_execution_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN: &str = "CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN";
const CONFIRM_FULL_BACKEND_CUTOVER_EXECUTION: &str = "CONFIRM_FULL_RUST_BACKEND_CUTOVER_EXECUTION_CONTRACT";

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

fn retirement_plan_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("pyretire-{}", &digest[..16])
}

fn side_effect_detected(payload: &Value, execution_contract: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("flask_routes_disabled"), false)
        || bool_value(payload.get("api_traffic_switched_to_rust"), false)
        || bool_value(payload.get("rust_service_runtime_authoritative"), false)
        || bool_value(payload.get("full_rust_backend_production_enabled"), false)
        || bool_value(payload.get("generated_files_written"), false)
        || bool_value(payload.get("libreqos_apply_executed"), false)
        || bool_value(payload.get("cleanup_authority_transferred"), false)
        || bool_value(payload.get("remove_python"), false)
        || bool_value(payload.get("disable_flask"), false)
        || bool_value(payload.get("execute_removal"), false)
        || bool_value(execution_contract.get("python_backend_removed"), false)
        || bool_value(execution_contract.get("full_rust_backend_production_enabled"), false)
        || bool_value(execution_contract.get("api_traffic_switched_to_rust"), false)
}

/// Build a non-mutating Python backend retirement plan.
///
/// v6.3 is the first explicit Python-retirement planning phase after the full
/// Rust backend cutover execution contract. It can mark the system as a
/// retirement candidate, but it still does not remove Python, disable Flask,
/// switch API traffic, or enable Rust production service authority.
pub fn build_python_backend_retirement_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "plan"),
            "execute" | "remove-python" | "disable-flask" | "replace-flask" | "switch-api" | "authoritative" | "production" | "cutover-now" | "enable"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "python_backend_retirement_execute_not_implemented",
            Some("python_backend_retirement_plan".to_string()),
            "This release only builds a Python backend retirement plan. It does not remove Python, disable Flask routes, switch API traffic, or enable Rust production authority.",
        ));
    }

    let allow_plan = bool_value(config_value(payload, "allow_python_backend_retirement_plan"), false);
    let plan_pilot = bool_value(config_value(payload, "python_backend_retirement_plan_pilot"), false);
    let retirement_mode = str_value(config_value(payload, "python_backend_retirement_mode"), "plan_only");
    let require_cutover_execution = bool_value(config_value(payload, "python_backend_retirement_require_cutover_execution_contract"), true);
    let require_python_fallback = bool_value(config_value(payload, "python_backend_retirement_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "python_backend_retirement_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "python_backend_retirement_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "python_backend_retirement_require_rollback_path"), true);
    let require_operator_ack = bool_value(config_value(payload, "python_backend_retirement_require_operator_ack"), true);
    let require_no_side_effects = bool_value(config_value(payload, "python_backend_retirement_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "python_backend_retirement_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_confirmation_required",
            Some("confirmation".to_string()),
            "Python backend retirement plan requires CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "python_backend_retirement_requires_python_fallback",
            Some("rust_core.python_backend_retirement_require_python_fallback".to_string()),
            "v6.3 still requires Python backend fallback. The actual Python removal belongs to a later explicit retirement execution package after server cargo tests, runtime cutover rehearsals, and rollback drills pass.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; Python retirement plan remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let execution_value = first_object(payload, &[
        "full_rust_backend_cutover_execution_contract",
        "full_backend_cutover_execution_contract",
        "full_rust_backend_cutover_execution",
    ]).cloned();

    let (execution_contract, execution_errors, mut execution_warnings) = match execution_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_cutover_execution_confirmation"),
                    CONFIRM_FULL_BACKEND_CUTOVER_EXECUTION,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_cutover_execution_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut execution_warnings);

    if !execution_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_cutover_execution_not_clean",
            Some("full_rust_backend_cutover_execution_contract".to_string()),
            "Full Rust backend cutover execution contract returned errors; Python retirement plan remains shadow-only.",
        ));
    }

    let execution_status = execution_contract.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let execution_ready = execution_errors.is_empty()
        && execution_status == "full_rust_backend_cutover_execution_contract_ready"
        && execution_contract.get("full_rust_backend_cutover_execution_contract_ready").and_then(Value::as_bool).unwrap_or(false)
        && execution_contract.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false
        && execution_contract.get("api_traffic_switched_to_rust").and_then(Value::as_bool).unwrap_or(false) == false
        && execution_contract.get("full_rust_backend_production_enabled").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_cutover_execution && !execution_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_cutover_execution_not_ready",
            Some("full_rust_backend_cutover_execution_contract".to_string()),
            "Full Rust backend cutover execution contract has not passed; Python backend retirement plan remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && execution_contract.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged for Python backend retirement planning.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "restore_python_backend_and_flask_routes");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_rollback_path_required",
            Some("rollback_path".to_string()),
            "Python backend retirement plan requires a rollback path before it can report ready.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_python_retirement_ack"), false)
        || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_operator_ack_required",
            Some("operator_python_retirement_ack".to_string()),
            "Python backend retirement plan requires operator acknowledgment.",
        ));
    }

    let side_effects = side_effect_detected(payload, &execution_contract);
    if require_no_side_effects && side_effects {
        errors.push(Diagnostic::error(
            "python_backend_retirement_side_effect_detected",
            Some("python_backend_retirement_plan".to_string()),
            "Python retirement planning detected mutation side effects. v6.3 is plan-only and must not remove Python, disable Flask, switch API traffic, or enable Rust production authority.",
        ));
    }

    let gates_ready = allow_plan && plan_pilot && retirement_mode == "plan_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_retirement_gates_not_enabled",
            Some("rust_core".to_string()),
            "Python backend retirement plan gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_cutover_execution || execution_ready)
        && shadow_age <= max_shadow_age
        && webui_unchanged
        && rollback_ready
        && operator_ack
        && require_python_fallback
        && !side_effects;

    let review = errors.is_empty() && execution_ready && webui_unchanged && rollback_ready && !side_effects;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "python_backend_retirement_plan_ready"
    } else if review {
        "python_backend_retirement_plan_review"
    } else {
        "python_backend_retirement_plan_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("execution_status".to_string(), json!(execution_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("python_backend_retirement_plan"));
    map.insert("status".to_string(), json!(status));
    map.insert("python_backend_retirement_plan_id".to_string(), json!(retirement_plan_id(&Value::Object(seed))));
    map.insert("python_backend_retirement_plan_ready".to_string(), json!(ready));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("operator_python_retirement_ack".to_string(), json!(operator_ack));
    map.insert("cutover_execution_contract_status".to_string(), json!(execution_status));
    map.insert("cutover_execution_contract_ready".to_string(), json!(execution_ready));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_removal_allowed".to_string(), json!(false));
    map.insert("flask_routes_disabled".to_string(), json!(false));
    map.insert("api_traffic_switched_to_rust".to_string(), json!(false));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(false));
    map.insert("generated_files_written".to_string(), json!(false));
    map.insert("libreqos_apply_executed".to_string(), json!(false));
    map.insert("next_stage".to_string(), json!("python_backend_retirement_execution_preflight"));
    map.insert("note".to_string(), json!("v6.3 builds the Python backend retirement plan after the full Rust backend cutover execution contract. It is still non-mutating: Python is not removed, Flask routes are not disabled, and API traffic is not switched."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_cutover_execution_contract() -> Value {
        json!({
            "status": "full_rust_backend_cutover_execution_contract_ready",
            "full_rust_backend_cutover_execution_contract_ready": true,
            "webui_ux_unchanged": true,
            "rollback_ready": true,
            "full_rust_backend_production_enabled": false,
            "python_backend_removed": false,
            "api_traffic_switched_to_rust": false,
            "python_backend_fallback_required": true
        })
    }

    fn ready_payload() -> Value {
        let mut rc = Map::new();
        rc.insert("allow_python_backend_retirement_plan".to_string(), json!(true));
        rc.insert("python_backend_retirement_plan_pilot".to_string(), json!(true));
        rc.insert("python_backend_retirement_mode".to_string(), json!("plan_only"));
        rc.insert("python_backend_retirement_require_cutover_execution_contract".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_python_fallback".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_manual_confirmation".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_webui_unchanged".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_rollback_path".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_operator_ack".to_string(), json!(true));
        rc.insert("python_backend_retirement_require_no_side_effects".to_string(), json!(true));
        rc.insert("python_backend_retirement_max_shadow_age_seconds".to_string(), json!(900));

        let mut root = Map::new();
        root.insert("rust_core".to_string(), Value::Object(rc));
        root.insert("confirmation".to_string(), json!(CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("restore_python_backend_and_flask_routes"));
        root.insert("operator_python_retirement_ack".to_string(), json!(true));
        root.insert("full_rust_backend_cutover_execution_contract".to_string(), ready_cutover_execution_contract());
        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only() {
        let (result, errors, _warnings) = build_python_backend_retirement_plan_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("python_backend_retirement_plan_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_python_backend_retirement_plan_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn reports_ready_without_removing_python() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_python_backend_retirement_plan_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("python_backend_retirement_plan_ready"));
        assert_eq!(result.get("python_backend_retirement_plan_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("api_traffic_switched_to_rust").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
    }
}
