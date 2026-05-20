use crate::collector_authority_production_switch::build_collector_authority_production_switch_contract_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_API_HANDOFF_PLAN: &str = "CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN";
const CONFIRM_PRODUCTION_SWITCH_CONTRACT: &str = "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT";

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

fn handoff_plan_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("apihandoff-{}", &digest[..16])
}

/// Build the Rust backend API handoff plan while keeping the existing WebUI/UX unchanged.
///
/// v5.1 starts the full-Rust-backend track after the collector-authority production
/// switch contract. It does not remove Python or replace Flask yet; it only proves
/// that a Rust API/service backend can be planned without changing the visible WebUI/UX.
pub fn build_rust_backend_api_handoff_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "plan"), "execute" | "commit" | "switch" | "remove-python" | "replace-flask" | "production" | "cutover");
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_backend_api_handoff_execute_not_implemented",
            Some("rust_backend_api_handoff_plan".to_string()),
            "This release only builds a Rust backend API handoff plan. It does not remove Python, replace Flask routes, switch API traffic, or change WebUI/UX.",
        ));
    }

    let allow_plan = bool_value(config_value(payload, "allow_rust_backend_api_handoff_plan"), false);
    let plan_pilot = bool_value(config_value(payload, "rust_backend_api_handoff_plan_pilot"), false);
    let handoff_mode = str_value(config_value(payload, "rust_backend_api_handoff_mode"), "plan_only");
    let require_switch_contract = bool_value(config_value(payload, "rust_backend_api_handoff_require_production_switch_contract"), true);
    let require_python_fallback = bool_value(config_value(payload, "rust_backend_api_handoff_require_python_backend_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "rust_backend_api_handoff_require_manual_confirmation"), true);
    let require_webui_compat = bool_value(config_value(payload, "rust_backend_api_handoff_require_webui_compatibility"), true);
    let require_route_parity = bool_value(config_value(payload, "rust_backend_api_handoff_require_route_parity"), true);
    let require_no_side_effects = bool_value(config_value(payload, "rust_backend_api_handoff_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "rust_backend_api_handoff_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_API_HANDOFF_PLAN;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_confirmation_required",
            Some("confirmation".to_string()),
            "Rust backend API handoff planning requires CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "rust_backend_api_handoff_requires_python_fallback",
            Some("rust_core.rust_backend_api_handoff_require_python_backend_fallback".to_string()),
            "v5.1 still requires the Python backend as fallback. Python removal belongs to later Rust API/scheduler/run_cycle/apply authority phases.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; API handoff plan remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let switch_value = first_object(payload, &[
        "collector_authority_production_switch_contract",
        "production_switch_contract",
        "collector_authority_switch_contract",
    ]).cloned();

    let (switch_contract, switch_errors, mut switch_warnings) = match switch_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let switch_confirmation = str_value(
                    payload.get("collector_authority_production_switch_confirmation"),
                    CONFIRM_PRODUCTION_SWITCH_CONTRACT,
                );
                obj.insert("confirmation".to_string(), json!(switch_confirmation));
            }
            build_collector_authority_production_switch_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut switch_warnings);

    if !switch_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_switch_contract_not_clean",
            Some("collector_authority_production_switch_contract".to_string()),
            "Production switch contract returned errors; Rust backend API handoff plan remains shadow-only.",
        ));
    }

    let switch_status = switch_contract.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let switch_ready = switch_errors.is_empty()
        && switch_status == "collector_authority_production_switch_contract_ready"
        && switch_contract.get("production_switch_contract_ready").and_then(Value::as_bool).unwrap_or(false)
        && switch_contract.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && switch_contract.get("python_backend_removable").and_then(Value::as_bool).unwrap_or(false) == false
        && switch_contract.get("python_backend_required").and_then(Value::as_bool).unwrap_or(true);

    if require_switch_contract && !switch_ready {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_switch_contract_not_ready",
            Some("collector_authority_production_switch_contract".to_string()),
            "Production switch contract has not passed; Rust backend API handoff plan remains shadow-only or under review.",
        ));
    }

    let webui_ux_unchanged = bool_value(payload.get("webui_ux_unchanged"), false);
    let webui_static_assets_unchanged = bool_value(payload.get("webui_static_assets_unchanged"), webui_ux_unchanged);
    let webui_compat_ready = !require_webui_compat || (webui_ux_unchanged && webui_static_assets_unchanged);
    if require_webui_compat && !webui_compat_ready {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_webui_compat_required",
            Some("webui_ux_unchanged".to_string()),
            "Rust backend API handoff requires the existing WebUI/UX and static assets to remain compatible and unchanged.",
        ));
    }

    let api_route_parity = bool_value(payload.get("api_route_parity"), false);
    let api_route_count = number_value(payload.get("api_route_count"), 0);
    let route_parity_ready = !require_route_parity || (api_route_parity && api_route_count > 0);
    if require_route_parity && !route_parity_ready {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_route_parity_required",
            Some("api_route_parity".to_string()),
            "Rust backend API handoff requires route parity inventory for the existing Python/Flask API surface.",
        ));
    }

    let cleanup_attempted = bool_value(payload.get("cleanup_attempted"), false);
    let apply_attempted = bool_value(payload.get("apply_attempted"), false);
    let write_attempted = bool_value(payload.get("write_attempted"), false);
    let python_removed = bool_value(payload.get("python_backend_removed"), false);
    let api_traffic_switched = bool_value(payload.get("api_traffic_switched_to_rust"), false);
    let side_effect_free = !cleanup_attempted && !apply_attempted && !write_attempted && !python_removed && !api_traffic_switched;

    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "rust_backend_api_handoff_side_effect_detected",
            Some("rust_backend_api_handoff_plan".to_string()),
            "API handoff plan detected cleanup/apply/write/Python-removal/API-switch side effects, which are forbidden in this release.",
        ));
    }

    let gates_ready = allow_plan && plan_pilot && handoff_mode == "plan_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "rust_backend_api_handoff_gates_not_enabled",
            Some("rust_core".to_string()),
            "Rust backend API handoff plan gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_switch_contract || switch_ready)
        && shadow_age <= max_shadow_age
        && require_python_fallback
        && webui_compat_ready
        && route_parity_ready
        && side_effect_free;

    let review = errors.is_empty() && switch_ready && webui_compat_ready && route_parity_ready && side_effect_free;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "rust_backend_api_handoff_plan_ready"
    } else if review {
        "rust_backend_api_handoff_plan_review"
    } else {
        "rust_backend_api_handoff_plan_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("switch_status".to_string(), json!(switch_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("route_count".to_string(), json!(api_route_count));

    let mut route_classes = Vec::new();
    for name in ["auth", "config", "collectors", "rust-core", "sync", "journal", "rollback", "monitoring"] {
        let mut item = Map::new();
        item.insert("class".to_string(), json!(name));
        item.insert("webui_contract".to_string(), json!("preserve_existing_ux"));
        item.insert("mutating".to_string(), json!(false));
        route_classes.push(Value::Object(item));
    }

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("rust_backend_api_handoff_plan"));
    map.insert("status".to_string(), json!(status));
    map.insert("api_handoff_plan_id".to_string(), json!(handoff_plan_id(&Value::Object(seed))));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_ux_unchanged));
    map.insert("webui_static_assets_unchanged".to_string(), json!(webui_static_assets_unchanged));
    map.insert("webui_compat_ready".to_string(), json!(webui_compat_ready));
    map.insert("api_route_parity".to_string(), json!(api_route_parity));
    map.insert("api_route_count".to_string(), json!(api_route_count));
    map.insert("route_parity_ready".to_string(), json!(route_parity_ready));
    map.insert("route_classes".to_string(), Value::Array(route_classes));
    map.insert("production_switch_status".to_string(), json!(switch_status));
    map.insert("production_switch_contract_ready".to_string(), json!(switch_ready));
    map.insert("rust_backend_api_handoff_ready".to_string(), json!(ready));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("api_traffic_switched_to_rust".to_string(), json!(false));
    map.insert("rust_api_service_authoritative".to_string(), json!(false));
    map.insert("rust_scheduler_authoritative".to_string(), json!(false));
    map.insert("rust_run_cycle_authoritative".to_string(), json!(false));
    map.insert("rust_apply_authoritative".to_string(), json!(false));
    map.insert("rust_can_drive_cleanup".to_string(), json!(false));
    map.insert("rust_can_drive_apply".to_string(), json!(false));
    map.insert("rust_can_write_generated_files".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("manual_confirmation_required".to_string(), json!(require_manual_confirmation));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("side_effect_free".to_string(), json!(side_effect_free));
    map.insert("next_stage".to_string(), json!("rust_scheduler_handoff_contract"));
    map.insert("note".to_string(), json!("v5.1 starts the full Rust backend track by planning Rust API/service handoff while preserving the existing WebUI/UX and keeping Python backend fallback required."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_API_HANDOFF_PLAN));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_assets_unchanged".to_string(), json!(true));
        root.insert("api_route_parity".to_string(), json!(true));
        root.insert("api_route_count".to_string(), json!(42));

        let mut rust_core = Map::new();
        rust_core.insert("allow_rust_backend_api_handoff_plan".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_plan_pilot".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_mode".to_string(), json!("plan_only"));
        rust_core.insert("rust_backend_api_handoff_require_production_switch_contract".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_require_python_backend_fallback".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_require_manual_confirmation".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_require_webui_compatibility".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_require_route_parity".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_require_no_side_effects".to_string(), json!(true));
        rust_core.insert("rust_backend_api_handoff_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rust_core));

        let mut switch_contract = Map::new();
        switch_contract.insert("status".to_string(), json!("collector_authority_production_switch_contract_ready"));
        switch_contract.insert("production_switch_contract_ready".to_string(), json!(true));
        switch_contract.insert("production_collector_authority_switched".to_string(), json!(false));
        switch_contract.insert("python_backend_removable".to_string(), json!(false));
        switch_contract.insert("python_backend_required".to_string(), json!(true));
        root.insert("collector_authority_production_switch_contract".to_string(), Value::Object(switch_contract));

        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_api_handoff_plan() {
        let (result, errors, _warnings) = build_rust_backend_api_handoff_plan_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_backend_api_handoff_plan_shadow_only"));
        assert_eq!(result.get("python_backend_removable").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("webui_compat_ready").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_and_python_removal_attempts() {
        let (result, errors, _warnings) = build_rust_backend_api_handoff_plan_payload(&json!({"execute": true, "mode":"remove-python"}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_api_handoff_plan_without_removing_python_or_changing_webui() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_rust_backend_api_handoff_plan_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_backend_api_handoff_plan_ready"));
        assert_eq!(result.get("rust_backend_api_handoff_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("webui_ux_unchanged").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("rust_api_service_authoritative").and_then(Value::as_bool), Some(false));
    }
}
