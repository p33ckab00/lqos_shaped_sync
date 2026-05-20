use crate::protocol::Diagnostic;
use crate::rust_backend_service_runtime_handoff::build_rust_backend_service_runtime_handoff_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_FULL_BACKEND_READINESS: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT";
const CONFIRM_SERVICE_RUNTIME_HANDOFF: &str = "CONFIRM_RUST_BACKEND_SERVICE_RUNTIME_HANDOFF_CONTRACT";

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

fn readiness_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("fullrustready-{}", &digest[..16])
}

/// Build the full Rust backend production-readiness contract.
///
/// v6.0 is the first full-backend production-readiness gate. It verifies that
/// all prior backend handoff layers have reached ready state, while still refusing
/// to remove Python or switch live traffic in this package. The WebUI/UX remains
/// unchanged and Python remains the fallback until a later explicit cutover/removal
/// package passes server-side tests.
pub fn build_full_rust_backend_production_readiness_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "commit" | "switch" | "remove-python" | "replace-flask" | "bind-live-api" | "production" | "authoritative" | "cutover"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_production_readiness_execute_not_implemented",
            Some("full_rust_backend_production_readiness_contract".to_string()),
            "This release only builds a full Rust backend production-readiness contract. It does not remove Python, disable Flask routes, switch API traffic, or claim production authority.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_full_rust_backend_production_readiness_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "full_rust_backend_production_readiness_contract_pilot"), false);
    let readiness_mode = str_value(config_value(payload, "full_rust_backend_production_readiness_mode"), "contract_only");
    let require_service_runtime = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_service_runtime"), true);
    let require_python_fallback = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_webui_unchanged"), true);
    let require_operator_final_review = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_operator_final_review"), true);
    let require_no_side_effects = bool_value(config_value(payload, "full_rust_backend_production_readiness_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_production_readiness_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_FULL_BACKEND_READINESS;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_confirmation_required",
            Some("confirmation".to_string()),
            "Full Rust backend production-readiness requires CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "full_rust_backend_production_readiness_requires_python_fallback",
            Some("rust_core.full_rust_backend_production_readiness_require_python_fallback".to_string()),
            "v6.0 still requires Python backend fallback. Python removal belongs to a later explicit production cutover/removal package.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; full backend production readiness remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let service_value = first_object(payload, &[
        "rust_backend_service_runtime_handoff_contract",
        "backend_service_runtime_handoff_contract",
        "rust_backend_service_runtime_handoff",
    ]).cloned();

    let (service_runtime_handoff, service_errors, mut service_warnings) = match service_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("rust_backend_service_runtime_handoff_confirmation"),
                    CONFIRM_SERVICE_RUNTIME_HANDOFF,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_rust_backend_service_runtime_handoff_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut service_warnings);

    if !service_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_service_runtime_not_clean",
            Some("rust_backend_service_runtime_handoff_contract".to_string()),
            "Rust backend service runtime handoff returned errors; full backend production-readiness remains shadow-only.",
        ));
    }

    let service_status = service_runtime_handoff.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let service_ready = service_errors.is_empty()
        && service_status == "rust_backend_service_runtime_handoff_contract_ready"
        && service_runtime_handoff.get("rust_backend_service_runtime_handoff_ready").and_then(Value::as_bool).unwrap_or(false)
        && service_runtime_handoff.get("rust_service_runtime_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && service_runtime_handoff.get("python_service_runtime_authoritative").and_then(Value::as_bool).unwrap_or(true);

    if require_service_runtime && !service_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_service_runtime_not_ready",
            Some("rust_backend_service_runtime_handoff_contract".to_string()),
            "Rust backend service runtime handoff contract has not passed; full backend production-readiness remains shadow-only or under review.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && service_runtime_handoff.get("webui_ux_unchanged").and_then(Value::as_bool).unwrap_or(true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX must remain unchanged for this readiness contract.",
        ));
    }

    let operator_final_review_ok = !require_operator_final_review
        || bool_value(payload.get("operator_final_review_ack"), false)
        || str_value(payload.get("operator_ack"), "") == "FULL_RUST_BACKEND_REVIEWED";
    if require_operator_final_review && !operator_final_review_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_operator_review_required",
            Some("operator_final_review_ack".to_string()),
            "Operator final review acknowledgement is required before full Rust backend production-readiness can report ready.",
        ));
    }

    let side_effect_detected = any_side_effect(payload)
        || service_runtime_handoff.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false)
        || service_runtime_handoff.get("api_traffic_switch_allowed").and_then(Value::as_bool).unwrap_or(false)
        || service_runtime_handoff.get("flask_disable_allowed").and_then(Value::as_bool).unwrap_or(false);
    if require_no_side_effects && side_effect_detected {
        errors.push(Diagnostic::error(
            "full_rust_backend_production_readiness_side_effect_detected",
            Some("full_rust_backend_production_readiness_contract".to_string()),
            "Full backend readiness detected Python removal, route disable, live API switch, write, apply, journal, rollback, or cleanup side effects, which are forbidden in this package.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && readiness_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_readiness_gates_not_enabled",
            Some("rust_core".to_string()),
            "Full Rust backend production-readiness gates are not fully enabled; contract remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_service_runtime || service_ready)
        && require_python_fallback
        && (!require_webui_unchanged || webui_unchanged)
        && operator_final_review_ok
        && !side_effect_detected
        && shadow_age <= max_shadow_age;

    let review = errors.is_empty() && service_ready && webui_unchanged && !side_effect_detected;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_production_readiness_contract_ready"
    } else if review {
        "full_rust_backend_production_readiness_contract_review"
    } else {
        "full_rust_backend_production_readiness_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("service_status".to_string(), json!(service_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_production_readiness_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("readiness_contract_id".to_string(), json!(readiness_id(&Value::Object(seed))));
    map.insert("full_rust_backend_production_readiness_ready".to_string(), json!(ready));
    map.insert("rust_backend_service_runtime_handoff_ready".to_string(), json!(service_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("operator_final_review_ack".to_string(), json!(operator_final_review_ok));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("full_rust_backend_candidate".to_string(), json!(ready));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_retirement_candidate".to_string(), json!(ready));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("python_service_runtime_authoritative".to_string(), json!(true));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(false));
    map.insert("python_api_routes_authoritative".to_string(), json!(true));
    map.insert("rust_api_routes_authoritative".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("api_traffic_switch_allowed".to_string(), json!(false));
    map.insert("flask_disable_allowed".to_string(), json!(false));
    map.insert("python_removal_allowed".to_string(), json!(false));
    map.insert("next_stage".to_string(), json!("full_rust_backend_production_cutover_and_python_retirement_plan"));
    map.insert("note".to_string(), json!("v6.0 builds the full Rust backend production-readiness contract. It can mark the system as a cutover candidate, but it still does not remove Python or switch live API/service authority."));

    (Value::Object(map), errors, warnings)
}

fn any_side_effect(payload: &Value) -> bool {
    bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("flask_routes_disabled"), false)
        || bool_value(payload.get("api_traffic_switched_to_rust"), false)
        || bool_value(payload.get("rust_backend_live_bound"), false)
        || bool_value(payload.get("service_runtime_switched_to_rust"), false)
        || bool_value(payload.get("rust_service_runtime_authoritative"), false)
        || bool_value(payload.get("rust_api_routes_authoritative"), false)
        || bool_value(payload.get("apply_attempted"), false)
        || bool_value(payload.get("cleanup_attempted"), false)
        || bool_value(payload.get("shaped_devices_write_attempted"), false)
        || bool_value(payload.get("journal_append_attempted"), false)
        || bool_value(payload.get("rollback_execute_attempted"), false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut payload = Map::new();
        payload.insert("confirmation".to_string(), json!(CONFIRM_FULL_BACKEND_READINESS));
        payload.insert("shadow_age_seconds".to_string(), json!(30));
        payload.insert("webui_ux_unchanged".to_string(), json!(true));
        payload.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        payload.insert("operator_final_review_ack".to_string(), json!(true));

        let mut rc = Map::new();
        rc.insert("allow_full_rust_backend_production_readiness_contract".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_contract_pilot".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_mode".to_string(), json!("contract_only"));
        rc.insert("full_rust_backend_production_readiness_require_service_runtime".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_require_python_fallback".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_require_manual_confirmation".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_require_webui_unchanged".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_require_operator_final_review".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_require_no_side_effects".to_string(), json!(true));
        rc.insert("full_rust_backend_production_readiness_max_shadow_age_seconds".to_string(), json!(900));
        payload.insert("rust_core".to_string(), Value::Object(rc));

        let mut service = Map::new();
        service.insert("status".to_string(), json!("rust_backend_service_runtime_handoff_contract_ready"));
        service.insert("rust_backend_service_runtime_handoff_ready".to_string(), json!(true));
        service.insert("rust_service_runtime_authoritative".to_string(), json!(false));
        service.insert("python_service_runtime_authoritative".to_string(), json!(true));
        service.insert("webui_ux_unchanged".to_string(), json!(true));
        service.insert("python_backend_removed".to_string(), json!(false));
        service.insert("api_traffic_switch_allowed".to_string(), json!(false));
        service.insert("flask_disable_allowed".to_string(), json!(false));
        payload.insert("rust_backend_service_runtime_handoff_contract".to_string(), Value::Object(service));

        Value::Object(payload)
    }

    #[test]
    fn defaults_to_shadow_only_full_backend_readiness() {
        let (result, errors, _warnings) = build_full_rust_backend_production_readiness_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_readiness_contract_shadow_only"));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("full_rust_backend_production_enabled").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = ready_payload();
        payload.as_object_mut().unwrap().insert("execute".to_string(), json!(true));
        let (result, errors, _warnings) = build_full_rust_backend_production_readiness_contract_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_full_backend_readiness_without_removing_python() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_full_rust_backend_production_readiness_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_readiness_contract_ready"));
        assert_eq!(result.get("full_rust_backend_production_readiness_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("full_rust_backend_production_enabled").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_removal_allowed").and_then(Value::as_bool), Some(false));
    }
}
