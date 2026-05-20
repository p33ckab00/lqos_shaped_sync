use crate::protocol::Diagnostic;
use crate::rust_full_backend_removal_rehearsal::build_full_rust_backend_removal_rehearsal_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER";
const CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL: &str = "CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL";

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
    format!("fullrust-cutover-{}", &digest[..16])
}

/// Build the v7.0 full Rust backend production cutover package.
///
/// v7.0 is the first final-production package. It still does not perform OS-level
/// mutation inside this core operation; instead it produces an auditable cutover
/// decision and requires the operator/supervisor to execute the generated cutover
/// scripts with an explicit confirmation token. This preserves WebUI/UX static
/// assets and prevents accidental Python removal without rollback preparation.
pub fn build_full_rust_backend_production_cutover_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let allow_cutover = bool_value(config_value(payload, "allow_full_rust_backend_production_cutover"), false);
    let cutover_pilot = bool_value(config_value(payload, "full_rust_backend_production_cutover_pilot"), false);
    let cutover_mode = str_value(config_value(payload, "full_rust_backend_production_cutover_mode"), "operator_supervised");
    let require_rehearsal = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_removal_rehearsal"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_manual_confirmation"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_webui_unchanged"), true);
    let require_rollback_path = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_rollback_path"), true);
    let require_operator_ack = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_operator_ack"), true);
    let require_server_tests = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_server_tests"), true);
    let require_python_fallback_backup = bool_value(config_value(payload, "full_rust_backend_production_cutover_require_python_fallback_backup"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_production_cutover_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_confirmation_required",
            Some("confirmation".to_string()),
            "Full Rust backend production cutover requires CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER before it can report ready.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; full Rust backend production cutover remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let rehearsal_value = first_object(payload, &[
        "full_rust_backend_removal_rehearsal",
        "full_rust_backend_removal_rehearsal_contract",
        "rust_full_backend_removal_rehearsal",
    ]).cloned();

    let (rehearsal, rehearsal_errors, mut rehearsal_warnings) = match rehearsal_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_removal_rehearsal_confirmation"),
                    CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_removal_rehearsal_payload(&nested_payload)
        }
    };
    warnings.append(&mut rehearsal_warnings);

    if !rehearsal_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_rehearsal_not_clean",
            Some("full_rust_backend_removal_rehearsal".to_string()),
            "Full Rust backend removal rehearsal returned errors; production cutover remains blocked.",
        ));
    }

    let rehearsal_status = rehearsal.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let rehearsal_ready = rehearsal_errors.is_empty()
        && rehearsal_status == "full_rust_backend_removal_rehearsal_ready"
        && rehearsal.get("full_rust_backend_candidate").and_then(Value::as_bool).unwrap_or(false)
        && rehearsal.get("python_backend_removal_candidate").and_then(Value::as_bool).unwrap_or(false)
        && rehearsal.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false) == false
        && rehearsal.get("api_traffic_switched_to_rust").and_then(Value::as_bool).unwrap_or(false) == false;

    if require_rehearsal && !rehearsal_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_rehearsal_not_ready",
            Some("full_rust_backend_removal_rehearsal".to_string()),
            "Full Rust backend removal rehearsal has not passed; production cutover is not allowed.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), true)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), true)
        && bool_value(payload.get("webui_static_assets_preserved"), true);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_webui_changed",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX and static asset paths must remain unchanged during full Rust backend production cutover.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "restore_python_backend_and_flask_routes");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_rollback_path_required",
            Some("rollback_path".to_string()),
            "Full Rust backend production cutover requires a rollback path before it can report ready.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_full_rust_backend_production_cutover_ack"), false)
        || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_operator_ack_required",
            Some("operator_full_rust_backend_production_cutover_ack".to_string()),
            "Full Rust backend production cutover requires operator acknowledgment.",
        ));
    }

    let server_tests_passed = bool_value(payload.get("server_cargo_tests_passed"), false)
        && bool_value(payload.get("self_test_passed"), false)
        && bool_value(payload.get("rollback_test_passed"), false);
    if require_server_tests && !server_tests_passed {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_server_tests_required",
            Some("server_cargo_tests_passed".to_string()),
            "Server cargo tests, self-test, and rollback test must pass before production cutover can be allowed.",
        ));
    }

    let python_fallback_backup_ready = bool_value(payload.get("python_fallback_backup_ready"), false)
        || bool_value(payload.get("python_backend_rollback_package_ready"), false);
    if require_python_fallback_backup && !python_fallback_backup_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_python_backup_required",
            Some("python_fallback_backup_ready".to_string()),
            "Python backend backup/rollback package must be ready before production cutover can be allowed.",
        ));
    }

    let gates_ready = allow_cutover && cutover_pilot && cutover_mode == "operator_supervised";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_production_cutover_gates_not_enabled",
            Some("rust_core".to_string()),
            "Full Rust backend production cutover gates are not fully enabled; report remains blocked or review-only.",
        ));
    }

    let cutover_allowed = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_rehearsal || rehearsal_ready)
        && webui_unchanged
        && rollback_ready
        && operator_ack
        && server_tests_passed
        && python_fallback_backup_ready
        && shadow_age <= max_shadow_age;

    let status = if !errors.is_empty() {
        "blocked"
    } else if cutover_allowed {
        "full_rust_backend_production_cutover_ready"
    } else if rehearsal_ready && webui_unchanged && rollback_ready {
        "full_rust_backend_production_cutover_review"
    } else {
        "full_rust_backend_production_cutover_blocked"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("rehearsal_status".to_string(), json!(rehearsal_status));
    seed.insert("cutover_allowed".to_string(), json!(cutover_allowed));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));

    let mut execution_steps = Vec::new();
    for (idx, name) in [
        "snapshot_python_backend_and_config",
        "start_rust_backend_service_authoritative_mode",
        "switch_api_traffic_to_rust_backend",
        "preserve_webui_static_assets",
        "disable_python_flask_service_after_healthcheck",
        "retain_python_rollback_package",
    ].iter().enumerate() {
        let mut step = Map::new();
        step.insert("step".to_string(), json!(idx + 1));
        step.insert("name".to_string(), json!(name));
        step.insert("requires_operator_supervision".to_string(), json!(true));
        execution_steps.push(Value::Object(step));
    }

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_production_cutover"));
    map.insert("status".to_string(), json!(status));
    map.insert("production_cutover_id".to_string(), json!(contract_id(&Value::Object(seed))));
    map.insert("cutover_allowed".to_string(), json!(cutover_allowed));
    map.insert("full_rust_backend".to_string(), json!(cutover_allowed));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(cutover_allowed));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(cutover_allowed));
    map.insert("api_traffic_switch_allowed".to_string(), json!(cutover_allowed));
    map.insert("python_backend_removable".to_string(), json!(cutover_allowed));
    map.insert("python_removal_allowed".to_string(), json!(cutover_allowed));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_removal_executed".to_string(), json!(false));
    map.insert("flask_routes_disabled".to_string(), json!(false));
    map.insert("api_traffic_switched_to_rust".to_string(), json!(false));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("webui_static_assets_preserved".to_string(), json!(true));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("server_tests_passed".to_string(), json!(server_tests_passed));
    map.insert("python_fallback_backup_ready".to_string(), json!(python_fallback_backup_ready));
    map.insert("rehearsal_status".to_string(), json!(rehearsal_status));
    map.insert("rehearsal_ready".to_string(), json!(rehearsal_ready));
    map.insert("operator_acknowledged".to_string(), json!(operator_ack));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("execution_steps".to_string(), Value::Array(execution_steps));
    map.insert("note".to_string(), json!("v7.0 is the first full Rust backend production cutover package. The Rust core declares whether cutover is allowed; OS-level service switching/removal must still be executed by the supervised cutover scripts with rollback ready."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER));
        root.insert("shadow_age_seconds".to_string(), json!(30));
        root.insert("operator_full_rust_backend_production_cutover_ack".to_string(), json!(true));
        root.insert("webui_ux_unchanged".to_string(), json!(true));
        root.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
        root.insert("webui_static_assets_preserved".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("restore_python_backend_and_flask_routes"));
        root.insert("server_cargo_tests_passed".to_string(), json!(true));
        root.insert("self_test_passed".to_string(), json!(true));
        root.insert("rollback_test_passed".to_string(), json!(true));
        root.insert("python_fallback_backup_ready".to_string(), json!(true));

        let mut rc = Map::new();
        rc.insert("allow_full_rust_backend_production_cutover".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_pilot".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_mode".to_string(), json!("operator_supervised"));
        rc.insert("full_rust_backend_production_cutover_require_removal_rehearsal".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_manual_confirmation".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_webui_unchanged".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_rollback_path".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_operator_ack".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_server_tests".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_require_python_fallback_backup".to_string(), json!(true));
        rc.insert("full_rust_backend_production_cutover_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut rehearsal = Map::new();
        rehearsal.insert("status".to_string(), json!("full_rust_backend_removal_rehearsal_ready"));
        rehearsal.insert("full_rust_backend_candidate".to_string(), json!(true));
        rehearsal.insert("python_backend_removal_candidate".to_string(), json!(true));
        rehearsal.insert("python_backend_removed".to_string(), json!(false));
        rehearsal.insert("api_traffic_switched_to_rust".to_string(), json!(false));
        root.insert("full_rust_backend_removal_rehearsal".to_string(), Value::Object(rehearsal));

        Value::Object(root)
    }

    #[test]
    fn defaults_to_blocked_cutover() {
        let (result, errors, _warnings) = build_full_rust_backend_production_cutover_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_cutover_blocked"));
        assert_eq!(result.get("cutover_allowed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn builds_ready_cutover_when_all_gates_are_met() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_full_rust_backend_production_cutover_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_cutover_ready"));
        assert_eq!(result.get("cutover_allowed").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("full_rust_backend_production_enabled").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_removed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("webui_ux_unchanged").and_then(Value::as_bool), Some(true));
    }
}
