use crate::protocol::Diagnostic;
use crate::rust_backend_production_enablement::build_rust_backend_production_enablement_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION: &str = "CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION_CONTRACT";
const CONFIRM_RUST_BACKEND_PRODUCTION_ENABLEMENT: &str = "CONFIRM_RUST_BACKEND_PRODUCTION_ENABLEMENT_CONTRACT";

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

fn contract_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("pyremove-{}", &digest[..16])
}

fn side_effect_detected(payload: &Value, enablement: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("flask_routes_disabled"), false)
        || bool_value(payload.get("api_traffic_switched_to_rust"), false)
        || bool_value(payload.get("rust_service_runtime_authoritative"), false)
        || bool_value(payload.get("full_rust_backend_production_enabled"), false)
        || bool_value(payload.get("generated_files_written"), false)
        || bool_value(payload.get("libreqos_apply_executed"), false)
        || bool_value(payload.get("remove_python"), false)
        || bool_value(payload.get("disable_flask"), false)
        || bool_value(payload.get("switch_api"), false)
        || bool_value(payload.get("execute_removal"), false)
        || bool_value(enablement.get("python_backend_removed"), false)
        || bool_value(enablement.get("api_traffic_switched_to_rust"), false)
        || bool_value(enablement.get("full_rust_backend_production_enabled"), false)
        || bool_value(enablement.get("rust_backend_production_enablement_allowed"), false)
}

/// Build a Python backend removal execution contract.
///
/// v6.5 is the first explicit Python-removal execution contract. It is still
/// non-mutating: it can declare that Python backend removal is an execution
/// candidate, but it does not remove Python files, disable Flask routes, switch
/// API traffic, or enable Rust as the production service authority. WebUI/UX
/// must remain unchanged.
pub fn build_python_backend_removal_execution_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "remove-python" | "disable-flask" | "switch-api" | "authoritative" | "production" | "cutover-now" | "delete-python"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "python_backend_removal_execution_not_implemented",
            Some("python_backend_removal_execution_contract".to_string()),
            "This release only builds a Python backend removal execution contract. It does not remove Python, disable Flask routes, switch API traffic, or enable Rust production authority.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_python_backend_removal_execution_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "python_backend_removal_execution_contract_pilot"), false);
    let removal_mode = str_value(config_value(payload, "python_backend_removal_execution_mode"), "contract_only");
    let require_enablement = bool_value(config_value(payload, "python_backend_removal_execution_require_rust_enablement_contract"), true);
    let require_python_fallback = bool_value(config_value(payload, "python_backend_removal_execution_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "python_backend_removal_execution_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "python_backend_removal_execution_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "python_backend_removal_execution_require_rollback_path"), true);
    let require_operator_ack = bool_value(config_value(payload, "python_backend_removal_execution_require_operator_ack"), true);
    let require_no_side_effects = bool_value(config_value(payload, "python_backend_removal_execution_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "python_backend_removal_execution_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_confirmation_required",
            Some("confirmation".to_string()),
            "Python backend removal execution contract requires CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "python_backend_removal_execution_requires_python_fallback",
            Some("rust_core.python_backend_removal_execution_require_python_fallback".to_string()),
            "v6.5 still requires Python backend fallback. Actual Python removal must be a later explicit mutating cutover package with rollback verification and server cargo tests.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; Python backend removal execution contract remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let enablement_value = first_object(payload, &[
        "rust_backend_production_enablement_contract",
        "rust_backend_enablement_contract",
        "rust_production_enablement_contract",
    ]).cloned();

    let (enablement, enablement_errors, mut enablement_warnings) = match enablement_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("rust_backend_production_enablement_confirmation"),
                    CONFIRM_RUST_BACKEND_PRODUCTION_ENABLEMENT,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_rust_backend_production_enablement_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut enablement_warnings);

    if !enablement_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_enablement_not_clean",
            Some("rust_backend_production_enablement_contract".to_string()),
            "Rust backend production enablement contract returned errors; Python backend removal execution contract remains shadow-only.",
        ));
    }

    let enablement_status = enablement.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let enablement_ready = enablement_errors.is_empty()
        && enablement_status == "rust_backend_production_enablement_contract_ready"
        && enablement.get("rust_backend_production_enablement_contract_ready").and_then(Value::as_bool).unwrap_or(false)
        && enablement.get("full_rust_backend_candidate").and_then(Value::as_bool).unwrap_or(false)
        && enablement.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false
        && enablement.get("api_traffic_switched_to_rust").and_then(Value::as_bool).unwrap_or(false) == false
        && enablement.get("rust_service_runtime_authoritative").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_enablement && !enablement_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_enablement_not_ready",
            Some("rust_backend_production_enablement_contract".to_string()),
            "Rust backend production enablement contract has not passed; Python backend removal execution contract remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && enablement.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged during Python backend removal planning.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "restore_python_backend_and_flask_routes");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_rollback_path_required",
            Some("rollback_path".to_string()),
            "Python backend removal execution contract requires a rollback path before it can report ready.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_python_backend_removal_execution_ack"), false)
        || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_operator_ack_required",
            Some("operator_python_backend_removal_execution_ack".to_string()),
            "Python backend removal execution contract requires operator acknowledgment.",
        ));
    }

    let side_effects = side_effect_detected(payload, &enablement);
    if require_no_side_effects && side_effects {
        errors.push(Diagnostic::error(
            "python_backend_removal_execution_side_effect_detected",
            Some("python_backend_removal_execution_contract".to_string()),
            "Python backend removal execution contract detected mutation side effects. v6.5 is contract-only and must not remove Python, disable Flask, switch API traffic, or enable Rust production authority.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && removal_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "python_backend_removal_execution_gates_not_enabled",
            Some("rust_core".to_string()),
            "Python backend removal execution contract gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_enablement || enablement_ready)
        && webui_unchanged
        && rollback_ready
        && operator_ack
        && require_python_fallback
        && !side_effects
        && shadow_age <= max_shadow_age;

    let review = errors.is_empty() && enablement_ready && webui_unchanged && rollback_ready && !side_effects;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "python_backend_removal_execution_contract_ready"
    } else if review {
        "python_backend_removal_execution_contract_review"
    } else {
        "python_backend_removal_execution_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("enablement_status".to_string(), json!(enablement_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("python_backend_removal_execution_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("python_backend_removal_execution_contract_id".to_string(), json!(contract_id(&Value::Object(seed))));
    map.insert("python_backend_removal_execution_contract_ready".to_string(), json!(ready));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("python_backend_removal_candidate".to_string(), json!(ready));
    map.insert("rust_backend_production_enablement_status".to_string(), json!(enablement_status));
    map.insert("rust_backend_production_enablement_ready".to_string(), json!(enablement_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("operator_python_backend_removal_execution_ack".to_string(), json!(operator_ack));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(false));
    map.insert("rust_backend_production_enablement_allowed".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_removal_allowed".to_string(), json!(false));
    map.insert("python_removal_executed".to_string(), json!(false));
    map.insert("flask_routes_disabled".to_string(), json!(false));
    map.insert("api_traffic_switched_to_rust".to_string(), json!(false));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(false));
    map.insert("generated_files_written".to_string(), json!(false));
    map.insert("libreqos_apply_executed".to_string(), json!(false));
    map.insert("webui_static_asset_paths_unchanged".to_string(), json!(bool_value(payload.get("webui_static_asset_paths_unchanged"), true)));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("next_stage".to_string(), json!("full_rust_backend_removal_rehearsal"));
    map.insert("note".to_string(), json!("v6.5 builds a non-mutating Python backend removal execution contract. It can mark a Python-removal candidate but cannot remove Python or switch backend/API traffic."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        root.insert("operator_python_backend_removal_execution_ack".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("restore_python_backend_and_flask_routes"));

        let mut rc = Map::new();
        rc.insert("python_backend_removal_execution_contract_pilot".to_string(), json!(true));
        rc.insert("allow_python_backend_removal_execution_contract".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_mode".to_string(), json!("contract_only"));
        rc.insert("python_backend_removal_execution_require_rust_enablement_contract".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_python_fallback".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_manual_confirmation".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_webui_unchanged".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_rollback_path".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_operator_ack".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_require_no_side_effects".to_string(), json!(true));
        rc.insert("python_backend_removal_execution_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut enablement = Map::new();
        enablement.insert("status".to_string(), json!("rust_backend_production_enablement_contract_ready"));
        enablement.insert("rust_backend_production_enablement_contract_ready".to_string(), json!(true));
        enablement.insert("full_rust_backend_candidate".to_string(), json!(true));
        enablement.insert("webui_ux_unchanged".to_string(), json!(true));
        enablement.insert("python_backend_removed".to_string(), json!(false));
        enablement.insert("api_traffic_switched_to_rust".to_string(), json!(false));
        enablement.insert("rust_service_runtime_authoritative".to_string(), json!(false));
        enablement.insert("full_rust_backend_production_enabled".to_string(), json!(false));
        enablement.insert("rust_backend_production_enablement_allowed".to_string(), json!(false));
        root.insert("rust_backend_production_enablement_contract".to_string(), Value::Object(enablement));

        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_removal_execution_contract() {
        let (result, errors, _warnings) = build_python_backend_removal_execution_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("python_backend_removal_execution_contract_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_python_backend_removal_execution_contract_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_removal_execution_contract_without_mutating() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_python_backend_removal_execution_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("python_backend_removal_execution_contract_ready"));
        assert_eq!(result.get("python_backend_removal_candidate").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("api_traffic_switched_to_rust").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
    }
}
