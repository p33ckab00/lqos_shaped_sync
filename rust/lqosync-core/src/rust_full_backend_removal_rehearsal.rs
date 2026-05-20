use crate::protocol::Diagnostic;
use crate::rust_python_backend_removal_execution::build_python_backend_removal_execution_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL: &str = "CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL";
const CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION: &str = "CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION_CONTRACT";

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
    format!("fullremove-rehearsal-{}", &digest[..16])
}

fn side_effect_detected(payload: &Value, removal: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("python_backend_removable"), false)
        || bool_value(payload.get("python_removal_allowed"), false)
        || bool_value(payload.get("python_removal_executed"), false)
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
        || bool_value(payload.get("execute_cutover"), false)
        || bool_value(removal.get("python_backend_removed"), false)
        || bool_value(removal.get("python_removal_allowed"), false)
        || bool_value(removal.get("python_removal_executed"), false)
        || bool_value(removal.get("api_traffic_switched_to_rust"), false)
        || bool_value(removal.get("full_rust_backend_production_enabled"), false)
        || bool_value(removal.get("rust_service_runtime_authoritative"), false)
}

/// Build the full Rust backend removal rehearsal contract.
///
/// v6.6 is the final non-mutating rehearsal before a future v7.0 actual cutover.
/// It verifies that the v6.5 Python-removal execution contract is ready and that
/// a rollback path/operator acknowledgment/WebUI compatibility are present. It
/// still does not remove Python, disable Flask routes, switch API traffic, or
/// enable Rust as production service authority.
pub fn build_full_rust_backend_removal_rehearsal_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "rehearsal"),
            "execute" | "remove-python" | "disable-flask" | "switch-api" | "authoritative" | "production" | "cutover-now" | "delete-python" | "enable-rust"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_removal_rehearsal_execute_not_implemented",
            Some("full_rust_backend_removal_rehearsal".to_string()),
            "This release only builds a full Rust backend removal rehearsal. It does not remove Python, disable Flask routes, switch API traffic, or enable Rust production authority.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_full_rust_backend_removal_rehearsal"), false);
    let contract_pilot = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_pilot"), false);
    let rehearsal_mode = str_value(config_value(payload, "full_rust_backend_removal_rehearsal_mode"), "rehearsal_only");
    let require_removal_contract = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_removal_execution_contract"), true);
    let require_python_fallback = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_rollback_path"), true);
    let require_operator_ack = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_operator_ack"), true);
    let require_no_side_effects = bool_value(config_value(payload, "full_rust_backend_removal_rehearsal_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_removal_rehearsal_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_confirmation_required",
            Some("confirmation".to_string()),
            "Full Rust backend removal rehearsal requires CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "full_rust_backend_removal_rehearsal_requires_python_fallback",
            Some("rust_core.full_rust_backend_removal_rehearsal_require_python_fallback".to_string()),
            "v6.6 still requires Python backend fallback. Actual Python removal must be a later explicit mutating v7.0 cutover package with rollback verification and server cargo tests.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; full Rust backend removal rehearsal remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let removal_value = first_object(payload, &[
        "python_backend_removal_execution_contract",
        "python_backend_removal_contract",
        "python_removal_execution_contract",
    ]).cloned();

    let (removal, removal_errors, mut removal_warnings) = match removal_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("python_backend_removal_execution_confirmation"),
                    CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_python_backend_removal_execution_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut removal_warnings);

    if !removal_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_removal_contract_not_clean",
            Some("python_backend_removal_execution_contract".to_string()),
            "Python backend removal execution contract returned errors; full Rust backend removal rehearsal remains shadow-only.",
        ));
    }

    let removal_status = removal.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let removal_ready = removal_errors.is_empty()
        && removal_status == "python_backend_removal_execution_contract_ready"
        && removal.get("python_backend_removal_execution_contract_ready").and_then(Value::as_bool).unwrap_or(false)
        && removal.get("full_rust_backend_candidate").and_then(Value::as_bool).unwrap_or(false)
        && removal.get("python_backend_removal_candidate").and_then(Value::as_bool).unwrap_or(false)
        && removal.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false
        && removal.get("api_traffic_switched_to_rust").and_then(Value::as_bool).unwrap_or(false) == false
        && removal.get("rust_service_runtime_authoritative").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_removal_contract && !removal_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_removal_contract_not_ready",
            Some("python_backend_removal_execution_contract".to_string()),
            "Python backend removal execution contract has not passed; full Rust backend removal rehearsal remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && removal.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged during full Rust backend removal rehearsal.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "restore_python_backend_and_flask_routes");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_rollback_path_required",
            Some("rollback_path".to_string()),
            "Full Rust backend removal rehearsal requires a rollback path before it can report ready.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_full_rust_backend_removal_rehearsal_ack"), false)
        || bool_value(payload.get("operator_python_backend_removal_execution_ack"), false)
        || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_operator_ack_required",
            Some("operator_full_rust_backend_removal_rehearsal_ack".to_string()),
            "Full Rust backend removal rehearsal requires operator acknowledgment.",
        ));
    }

    let side_effects = side_effect_detected(payload, &removal);
    if require_no_side_effects && side_effects {
        errors.push(Diagnostic::error(
            "full_rust_backend_removal_rehearsal_side_effect_detected",
            Some("full_rust_backend_removal_rehearsal".to_string()),
            "Full Rust backend removal rehearsal detected mutation side effects. v6.6 is rehearsal-only and must not remove Python, disable Flask, switch API traffic, or enable Rust production authority.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && rehearsal_mode == "rehearsal_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_removal_rehearsal_gates_not_enabled",
            Some("rust_core".to_string()),
            "Full Rust backend removal rehearsal gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_removal_contract || removal_ready)
        && webui_unchanged
        && rollback_ready
        && operator_ack
        && require_python_fallback
        && !side_effects
        && shadow_age <= max_shadow_age;

    let review = errors.is_empty() && removal_ready && webui_unchanged && rollback_ready && !side_effects;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_removal_rehearsal_ready"
    } else if review {
        "full_rust_backend_removal_rehearsal_review"
    } else {
        "full_rust_backend_removal_rehearsal_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("removal_status".to_string(), json!(removal_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_removal_rehearsal"));
    map.insert("status".to_string(), json!(status));
    map.insert("full_rust_backend_removal_rehearsal_id".to_string(), json!(contract_id(&Value::Object(seed))));
    map.insert("full_rust_backend_removal_rehearsal_ready".to_string(), json!(ready));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("python_backend_removal_candidate".to_string(), json!(ready));
    map.insert("python_backend_removal_execution_status".to_string(), json!(removal_status));
    map.insert("python_backend_removal_execution_ready".to_string(), json!(removal_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("operator_full_rust_backend_removal_rehearsal_ack".to_string(), json!(operator_ack));
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
    map.insert("next_stage".to_string(), json!("v7_actual_full_rust_backend_cutover_python_removal"));
    map.insert("note".to_string(), json!("v6.6 builds the final non-mutating full Rust backend removal rehearsal. It can mark a removal rehearsal candidate but cannot remove Python or switch backend/API traffic."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        root.insert("operator_full_rust_backend_removal_rehearsal_ack".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("restore_python_backend_and_flask_routes"));

        let mut rc = Map::new();
        rc.insert("full_rust_backend_removal_rehearsal_pilot".to_string(), json!(true));
        rc.insert("allow_full_rust_backend_removal_rehearsal".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_mode".to_string(), json!("rehearsal_only"));
        rc.insert("full_rust_backend_removal_rehearsal_require_removal_execution_contract".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_python_fallback".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_manual_confirmation".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_webui_unchanged".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_rollback_path".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_operator_ack".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_require_no_side_effects".to_string(), json!(true));
        rc.insert("full_rust_backend_removal_rehearsal_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut removal = Map::new();
        removal.insert("status".to_string(), json!("python_backend_removal_execution_contract_ready"));
        removal.insert("python_backend_removal_execution_contract_ready".to_string(), json!(true));
        removal.insert("full_rust_backend_candidate".to_string(), json!(true));
        removal.insert("python_backend_removal_candidate".to_string(), json!(true));
        removal.insert("webui_ux_unchanged".to_string(), json!(true));
        removal.insert("python_backend_removed".to_string(), json!(false));
        removal.insert("python_removal_allowed".to_string(), json!(false));
        removal.insert("python_removal_executed".to_string(), json!(false));
        removal.insert("api_traffic_switched_to_rust".to_string(), json!(false));
        removal.insert("rust_service_runtime_authoritative".to_string(), json!(false));
        removal.insert("full_rust_backend_production_enabled".to_string(), json!(false));
        root.insert("python_backend_removal_execution_contract".to_string(), Value::Object(removal));

        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_full_rust_backend_removal_rehearsal() {
        let (result, errors, _warnings) = build_full_rust_backend_removal_rehearsal_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_removal_rehearsal_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_full_rust_backend_removal_rehearsal_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_removal_rehearsal_without_mutating() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_full_rust_backend_removal_rehearsal_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_removal_rehearsal_ready"));
        assert_eq!(result.get("full_rust_backend_removal_rehearsal_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("api_traffic_switched_to_rust").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
    }
}
