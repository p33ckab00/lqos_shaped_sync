use crate::protocol::Diagnostic;
use crate::rust_full_backend_cutover_plan::build_full_rust_backend_cutover_plan_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_FULL_BACKEND_CUTOVER_EXECUTION: &str = "CONFIRM_FULL_RUST_BACKEND_CUTOVER_EXECUTION_CONTRACT";
const CONFIRM_FULL_BACKEND_CUTOVER_PLAN: &str = "CONFIRM_FULL_RUST_BACKEND_CUTOVER_PLAN";

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

fn execution_contract_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("fullrustexec-{}", &digest[..16])
}

fn side_effect_detected(payload: &Value, cutover_plan: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("flask_routes_disabled"), false)
        || bool_value(payload.get("api_traffic_switched_to_rust"), false)
        || bool_value(payload.get("rust_service_runtime_authoritative"), false)
        || bool_value(payload.get("full_rust_backend_production_enabled"), false)
        || bool_value(payload.get("generated_files_written"), false)
        || bool_value(payload.get("libreqos_apply_executed"), false)
        || bool_value(payload.get("cleanup_authority_transferred"), false)
        || bool_value(payload.get("remove_python"), false)
        || bool_value(cutover_plan.get("python_backend_removed"), false)
        || bool_value(cutover_plan.get("full_rust_backend_production_enabled"), false)
}

/// Build the full Rust backend cutover execution contract.
///
/// v6.2 is the first execution-contract bridge after the v6.1 cutover plan.
/// It deliberately remains non-mutating. It can prove that cutover execution
/// gates are present, but it does not remove Python, disable Flask, switch API
/// traffic, or enable Rust production authority. WebUI/UX remains unchanged.
pub fn build_full_rust_backend_cutover_execution_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "remove-python" | "replace-flask" | "bind-live-api" | "switch" | "authoritative" | "production" | "cutover-now" | "enable"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_execution_not_implemented",
            Some("full_rust_backend_cutover_execution_contract".to_string()),
            "This release only builds a full Rust backend cutover execution contract. It does not remove Python, disable Flask routes, switch API traffic, or enable Rust production authority.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_full_rust_backend_cutover_execution_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "full_rust_backend_cutover_execution_contract_pilot"), false);
    let cutover_mode = str_value(config_value(payload, "full_rust_backend_cutover_execution_mode"), "contract_only");
    let require_cutover_plan = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_cutover_plan"), true);
    let require_python_fallback = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_rollback_path"), true);
    let require_operator_execution_ack = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_operator_ack"), true);
    let require_no_side_effects = bool_value(config_value(payload, "full_rust_backend_cutover_execution_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_cutover_execution_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_FULL_BACKEND_CUTOVER_EXECUTION;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_confirmation_required",
            Some("confirmation".to_string()),
            "Full Rust backend cutover execution contract requires CONFIRM_FULL_RUST_BACKEND_CUTOVER_EXECUTION_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_execution_requires_python_fallback",
            Some("rust_core.full_rust_backend_cutover_execution_require_python_fallback".to_string()),
            "v6.2 still requires Python backend fallback. Python removal belongs to a later explicit retirement/removal package after server cargo tests and runtime cutover rehearsals pass.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; full backend cutover execution contract remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let cutover_plan_value = first_object(payload, &[
        "full_rust_backend_cutover_plan",
        "full_backend_cutover_plan",
        "full_rust_backend_cutover_plan_contract",
    ]).cloned();

    let (cutover_plan, plan_errors, mut plan_warnings) = match cutover_plan_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_cutover_plan_confirmation"),
                    CONFIRM_FULL_BACKEND_CUTOVER_PLAN,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_cutover_plan_payload(&nested_payload)
        }
    };
    warnings.append(&mut plan_warnings);

    if !plan_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_plan_not_clean",
            Some("full_rust_backend_cutover_plan".to_string()),
            "Full Rust backend cutover plan returned errors; execution contract remains shadow-only.",
        ));
    }

    let plan_status = cutover_plan.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let cutover_plan_ready = plan_errors.is_empty()
        && plan_status == "full_rust_backend_cutover_plan_ready"
        && cutover_plan.get("full_rust_backend_cutover_plan_ready").and_then(Value::as_bool).unwrap_or(false)
        && cutover_plan.get("full_rust_backend_production_enabled").and_then(Value::as_bool).unwrap_or(false) == false
        && cutover_plan.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false
        && cutover_plan.get("api_traffic_switched_to_rust").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_cutover_plan && !cutover_plan_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_plan_not_ready",
            Some("full_rust_backend_cutover_plan".to_string()),
            "Full Rust backend cutover plan has not passed; execution contract remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && cutover_plan.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged for this cutover execution contract.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "python_backend_reenable_and_flask_route_restore");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_rollback_path_required",
            Some("rollback_path".to_string()),
            "A Python backend rollback path is required before the cutover execution contract can report ready.",
        ));
    }

    let operator_execution_ack = !require_operator_execution_ack
        || bool_value(payload.get("operator_cutover_execution_ack"), false)
        || str_value(payload.get("operator_ack"), "") == "FULL_RUST_BACKEND_CUTOVER_EXECUTION_REVIEWED";
    if require_operator_execution_ack && !operator_execution_ack {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_operator_ack_required",
            Some("operator_cutover_execution_ack".to_string()),
            "Operator execution acknowledgment is required before full Rust backend cutover execution contract can report ready.",
        ));
    }

    let side_effects = side_effect_detected(payload, &cutover_plan);
    if require_no_side_effects && side_effects {
        errors.push(Diagnostic::error(
            "full_rust_backend_cutover_execution_side_effect_detected",
            Some("full_rust_backend_cutover_execution_contract".to_string()),
            "Cutover execution contract detected Python removal, Flask disablement, API switch, generated writes, or production authority side effects, which are forbidden in this package.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && cutover_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_cutover_execution_gates_not_enabled",
            Some("rust_core".to_string()),
            "Full Rust backend cutover execution-contract gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_cutover_plan || cutover_plan_ready)
        && shadow_age <= max_shadow_age
        && webui_unchanged
        && rollback_ready
        && operator_execution_ack
        && require_python_fallback
        && !side_effects;

    let review = errors.is_empty() && cutover_plan_ready && webui_unchanged && rollback_ready && !side_effects;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_cutover_execution_contract_ready"
    } else if review {
        "full_rust_backend_cutover_execution_contract_review"
    } else {
        "full_rust_backend_cutover_execution_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("cutover_plan_status".to_string(), json!(plan_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_cutover_execution_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("cutover_execution_contract_id".to_string(), json!(execution_contract_id(&Value::Object(seed))));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("full_rust_backend_cutover_execution_contract_ready".to_string(), json!(ready));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("operator_cutover_execution_ack".to_string(), json!(operator_execution_ack));
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
    map.insert("next_stage".to_string(), json!("full_rust_backend_enablement_and_python_retirement_preflight"));
    map.insert("note".to_string(), json!("v6.2 builds the full Rust backend cutover execution contract. It is still non-mutating: Python is not removed and API traffic is not switched."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_cutover_plan() -> Value {
        json!({
            "status": "full_rust_backend_cutover_plan_ready",
            "full_rust_backend_cutover_plan_ready": true,
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
        rc.insert("allow_full_rust_backend_cutover_execution_contract".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_contract_pilot".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_mode".to_string(), json!("contract_only"));
        rc.insert("full_rust_backend_cutover_execution_require_cutover_plan".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_python_fallback".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_manual_confirmation".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_webui_unchanged".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_rollback_path".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_operator_ack".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_require_no_side_effects".to_string(), json!(true));
        rc.insert("full_rust_backend_cutover_execution_max_shadow_age_seconds".to_string(), json!(900));

        let mut root = Map::new();
        root.insert("rust_core".to_string(), Value::Object(rc));
        root.insert("confirmation".to_string(), json!(CONFIRM_FULL_BACKEND_CUTOVER_EXECUTION));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("python_backend_reenable_and_flask_route_restore"));
        root.insert("operator_cutover_execution_ack".to_string(), json!(true));
        root.insert("full_rust_backend_cutover_plan".to_string(), ready_cutover_plan());
        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only() {
        let (result, errors, _warnings) = build_full_rust_backend_cutover_execution_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_cutover_execution_contract_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_full_rust_backend_cutover_execution_contract_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn reports_ready_without_removing_python() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_full_rust_backend_cutover_execution_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_cutover_execution_contract_ready"));
        assert_eq!(result.get("full_rust_backend_cutover_execution_contract_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("api_traffic_switched_to_rust").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
    }
}
