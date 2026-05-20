use crate::protocol::Diagnostic;
use crate::rust_full_backend_production_readiness::build_full_rust_backend_production_readiness_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_FULL_BACKEND_CUTOVER_PLAN: &str = "CONFIRM_FULL_RUST_BACKEND_CUTOVER_PLAN";
const CONFIRM_FULL_BACKEND_READINESS: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT";

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

fn cutover_plan_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("fullrustcutover-{}", &digest[..16])
}

fn side_effect_detected(payload: &Value, readiness: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("flask_routes_disabled"), false)
        || bool_value(payload.get("api_traffic_switched_to_rust"), false)
        || bool_value(payload.get("rust_service_runtime_authoritative"), false)
        || bool_value(payload.get("generated_files_written"), false)
        || bool_value(payload.get("libreqos_apply_executed"), false)
        || bool_value(payload.get("cleanup_authority_transferred"), false)
        || bool_value(payload.get("remove_python"), false)
        || bool_value(readiness.get("python_backend_removed"), false)
        || bool_value(readiness.get("full_rust_backend_production_enabled"), false)
}

/// Build the full Rust backend cutover plan.
///
/// v6.1 is a cutover planning gate after v6.0 production-readiness. It is still
/// non-mutating: it does not remove Python, disable Flask, switch API traffic, or
/// mark Rust as production-authoritative. It makes the final cutover sequence
/// auditable while preserving the existing WebUI/UX and Python rollback path.
pub fn build_full_rust_backend_cutover_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "plan"),
            "execute" | "remove-python" | "replace-flask" | "bind-live-api" | "switch" | "authoritative" | "production" | "cutover-now"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_execute_not_implemented",
            Some("full_rust_backend_cutover_plan".to_string()),
            "This release only builds a full Rust backend cutover plan. It does not remove Python, disable Flask routes, switch API traffic, or enable Rust production authority.",
        ));
    }

    let allow_plan = bool_value(config_value(payload, "allow_full_rust_backend_cutover_plan"), false);
    let plan_pilot = bool_value(config_value(payload, "full_rust_backend_cutover_plan_pilot"), false);
    let cutover_mode = str_value(config_value(payload, "full_rust_backend_cutover_mode"), "plan_only");
    let require_readiness = bool_value(config_value(payload, "full_rust_backend_cutover_require_production_readiness"), true);
    let require_python_fallback = bool_value(config_value(payload, "full_rust_backend_cutover_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_cutover_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_cutover_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "full_rust_backend_cutover_require_rollback_path"), true);
    let require_operator_approval = bool_value(config_value(payload, "full_rust_backend_cutover_require_operator_approval"), true);
    let require_no_side_effects = bool_value(config_value(payload, "full_rust_backend_cutover_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_cutover_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_FULL_BACKEND_CUTOVER_PLAN;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_confirmation_required",
            Some("confirmation".to_string()),
            "Full Rust backend cutover plan requires CONFIRM_FULL_RUST_BACKEND_CUTOVER_PLAN before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_requires_python_fallback",
            Some("rust_core.full_rust_backend_cutover_require_python_fallback".to_string()),
            "v6.1 still requires Python backend fallback. Python removal belongs to the later final retirement/removal package after server cargo tests pass.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; full backend cutover plan remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let readiness_value = first_object(payload, &[
        "full_rust_backend_production_readiness_contract",
        "full_rust_backend_readiness_contract",
        "full_backend_production_readiness_contract",
    ]).cloned();

    let (readiness, readiness_errors, mut readiness_warnings) = match readiness_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_production_readiness_confirmation"),
                    CONFIRM_FULL_BACKEND_READINESS,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_production_readiness_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut readiness_warnings);

    if !readiness_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_readiness_not_clean",
            Some("full_rust_backend_production_readiness_contract".to_string()),
            "Full Rust backend production-readiness contract returned errors; cutover plan remains shadow-only.",
        ));
    }

    let readiness_status = readiness.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let readiness_ready = readiness_errors.is_empty()
        && readiness_status == "full_rust_backend_production_readiness_contract_ready"
        && readiness.get("full_rust_backend_production_readiness_ready").and_then(Value::as_bool).unwrap_or(false)
        && readiness.get("full_rust_backend_production_enabled").and_then(Value::as_bool).unwrap_or(false) == false
        && readiness.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_readiness && !readiness_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_readiness_not_ready",
            Some("full_rust_backend_production_readiness_contract".to_string()),
            "Full Rust backend production-readiness contract has not passed; cutover plan remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && readiness.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged for this cutover plan.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "python_backend_reenable_and_flask_route_restore");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_rollback_path_required",
            Some("rollback_path".to_string()),
            "A Python backend rollback path is required before cutover planning can report ready.",
        ));
    }

    let operator_approved = !require_operator_approval
        || bool_value(payload.get("operator_cutover_approval_ack"), false)
        || str_value(payload.get("operator_ack"), "") == "FULL_RUST_BACKEND_CUTOVER_REVIEWED";
    if require_operator_approval && !operator_approved {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_operator_approval_required",
            Some("operator_cutover_approval_ack".to_string()),
            "Operator cutover approval is required before full Rust backend cutover planning can report ready.",
        ));
    }

    let side_effects = side_effect_detected(payload, &readiness);
    if require_no_side_effects && side_effects {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_side_effect_detected",
            Some("full_rust_backend_cutover_plan".to_string()),
            "Cutover planning detected Python removal, Flask disablement, API switch, generated writes, or production authority side effects, which are forbidden in this package.",
        ));
    }

    let gates_ready = allow_plan && plan_pilot && cutover_mode == "plan_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_gates_not_enabled",
            Some("rust_core".to_string()),
            "Full Rust backend cutover-plan gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_readiness || readiness_ready)
        && shadow_age <= max_shadow_age
        && webui_unchanged
        && rollback_ready
        && operator_approved
        && require_python_fallback
        && !side_effects;

    let review = errors.is_empty() && readiness_ready && webui_unchanged && rollback_ready && !side_effects;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_cutover_plan_ready"
    } else if review {
        "full_rust_backend_cutover_plan_review"
    } else {
        "full_rust_backend_cutover_plan_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("readiness_status".to_string(), json!(readiness_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_cutover_plan"));
    map.insert("status".to_string(), json!(status));
    map.insert("cutover_plan_id".to_string(), json!(cutover_plan_id(&Value::Object(seed))));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("full_rust_backend_cutover_plan_ready".to_string(), json!(ready));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("operator_cutover_approval_ok".to_string(), json!(operator_approved));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("production_readiness_status".to_string(), json!(readiness_status));
    map.insert("production_readiness_ready".to_string(), json!(readiness_ready));
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
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("next_stage".to_string(), json!("python_backend_retirement_and_rust_service_cutover_package"));
    map.insert("note".to_string(), json!("v6.1 builds a non-mutating full Rust backend cutover plan. It does not remove Python or switch live API traffic; Python retirement belongs to a later explicit package after server-side cargo tests pass."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut payload = Map::new();
        payload.insert("confirmation".to_string(), json!(CONFIRM_FULL_BACKEND_CUTOVER_PLAN));
        payload.insert("shadow_age_seconds".to_string(), json!(30));
        payload.insert("webui_ux_unchanged".to_string(), json!(true));
        payload.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        payload.insert("operator_cutover_approval_ack".to_string(), json!(true));
        payload.insert("rollback_path".to_string(), json!("python_backend_reenable_and_flask_route_restore"));

        let mut rc = Map::new();
        rc.insert("allow_full_rust_backend_cutover_plan".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_plan_pilot".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_mode".to_string(), json!("plan_only"));
        rc.insert("full_rust_backend_cutover_require_production_readiness".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_python_fallback".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_manual_confirmation".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_webui_unchanged".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_rollback_path".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_operator_approval".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_require_no_side_effects".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_max_shadow_age_seconds".to_string(), json!(900));
        payload.insert("rust_core".to_string(), Value::Object(rc));

        let mut readiness = Map::new();
        readiness.insert("status".to_string(), json!("full_rust_backend_production_readiness_contract_ready"));
        readiness.insert("full_rust_backend_production_readiness_ready".to_string(), json!(true));
        readiness.insert("full_rust_backend_production_enabled".to_string(), json!(false));
        readiness.insert("python_backend_removed".to_string(), json!(false));
        readiness.insert("webui_ux_unchanged".to_string(), json!(true));
        payload.insert("full_rust_backend_production_readiness_contract".to_string(), Value::Object(readiness));

        Value::Object(payload)
    }

    #[test]
    fn defaults_to_shadow_only_cutover_plan() {
        let (result, errors, _warnings) = build_full_rust_backend_cutover_plan_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_cutover_plan_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_full_rust_backend_cutover_plan_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_cutover_plan_without_removing_python() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_full_rust_backend_cutover_plan_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_cutover_plan_ready"));
        assert_eq!(result.get("full_rust_backend_cutover_plan_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("webui_ux_unchanged").and_then(Value::as_bool), Some(true));
    }
}
