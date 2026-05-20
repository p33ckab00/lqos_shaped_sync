use crate::protocol::Diagnostic;
use crate::rust_full_backend_steady_state_guard::build_full_rust_backend_steady_state_guard_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_DRIFT_MONITOR: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR";
const CONFIRM_STEADY_STATE_GUARD: &str = "CONFIRM_FULL_RUST_BACKEND_STEADY_STATE_GUARD";

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

fn drift_monitor_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("fullrust-drift-{}", &digest[..16])
}

/// Build the v7.4 production drift monitor for a fully migrated Rust backend.
///
/// This is a post-steady-state guard. It verifies that the production system has
/// not drifted back to Python, that Rust runtime authority remains healthy, that
/// WebUI/static assets remain unchanged, and that rollback is still available.
/// It is intentionally non-mutating: no service restart, no file deletion, no
/// traffic switch, no LibreQoS apply.
pub fn build_full_rust_backend_production_drift_monitor_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "monitor"), "execute" | "repair" | "delete" | "disable" | "restart" | "switch" | "rollback");
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_production_drift_monitor_execute_not_implemented",
            Some("full_rust_backend_production_drift_monitor".to_string()),
            "The production drift monitor is verification-only. It does not mutate services, delete Python files, switch traffic, or execute rollback.",
        ));
    }

    let allow_monitor = bool_value(config_value(payload, "allow_full_rust_backend_production_drift_monitor"), false);
    let monitor_pilot = bool_value(config_value(payload, "full_rust_backend_production_drift_monitor_pilot"), false);
    let monitor_mode = str_value(config_value(payload, "full_rust_backend_production_drift_monitor_mode"), "monitor_only");
    let require_steady_state = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_steady_state_guard"), true);
    let require_runtime_health = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_runtime_health"), true);
    let require_no_drift = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_no_python_drift"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_webui_unchanged"), true);
    let require_rollback_package = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_rollback_package"), true);
    let require_server_tests = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_server_tests"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_manual_confirmation"), true);
    let require_operator_ack = bool_value(config_value(payload, "full_rust_backend_drift_monitor_require_operator_ack"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_drift_monitor_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_DRIFT_MONITOR;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_confirmation_required",
            Some("confirmation".to_string()),
            "Production drift monitor requires CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR before it can report monitored/healthy.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_stale",
            Some("shadow_age_seconds".to_string()),
            "Production drift observations are older than the configured maximum age.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let steady_state_value = first_object(payload, &[
        "full_rust_backend_steady_state_guard",
        "full_rust_backend_steady_state_guard_contract",
        "rust_full_backend_steady_state_guard",
    ]).cloned();

    let (steady_state, steady_state_errors, mut steady_state_warnings) = match steady_state_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_steady_state_guard_confirmation"),
                    CONFIRM_STEADY_STATE_GUARD,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_steady_state_guard_payload(&nested_payload)
        }
    };
    warnings.append(&mut steady_state_warnings);

    let steady_state_status = steady_state.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let steady_state_ready = steady_state_errors.is_empty()
        && steady_state_status == "full_rust_backend_steady_state_verified"
        && steady_state.get("full_rust_backend").and_then(Value::as_bool).unwrap_or(false)
        && steady_state.get("python_drift_absent").and_then(Value::as_bool).unwrap_or(false);
    if require_steady_state && !steady_state_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_steady_state_not_ready",
            Some("full_rust_backend_steady_state_guard".to_string()),
            "Steady-state guard has not verified; production drift monitor remains blocked or review-only.",
        ));
    }

    let rust_runtime_ready = bool_value(payload.get("rust_service_active"), false)
        && bool_value(payload.get("rust_api_healthcheck_passed"), false)
        && (bool_value(payload.get("rust_unix_socket_active"), false) || bool_value(payload.get("rust_http_api_active"), false))
        && bool_value(payload.get("rust_service_runtime_authoritative"), false)
        && bool_value(payload.get("api_traffic_switched_to_rust"), false);
    if require_runtime_health && !rust_runtime_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_runtime_health_required",
            Some("rust_service_active".to_string()),
            "Rust runtime, healthcheck, socket/API, API route, and service authority must remain healthy.",
        ));
    }

    let drift_check_count = number_value(payload.get("drift_check_count"), 0);
    let python_process_count = number_value(payload.get("python_backend_process_count"), 0);
    let python_drift_absent = bool_value(payload.get("flask_routes_disabled"), false)
        && bool_value(payload.get("python_backend_stopped_or_disabled"), false)
        && (bool_value(payload.get("python_backend_service_masked_or_disabled"), false) || bool_value(payload.get("python_backend_service_removed"), false))
        && !bool_value(payload.get("python_backend_unexpectedly_running"), false)
        && !bool_value(payload.get("flask_routes_reappeared"), false)
        && !bool_value(payload.get("api_traffic_routed_to_python"), false)
        && !bool_value(payload.get("python_backend_service_reenabled"), false)
        && python_process_count == 0
        && drift_check_count > 0;
    if require_no_drift && !python_drift_absent {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_python_drift_detected",
            Some("python_backend_unexpectedly_running".to_string()),
            "Python/Flask backend drift signals must remain absent and at least one drift check must run.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), false)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), false)
        && bool_value(payload.get("webui_static_assets_preserved"), false);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_webui_unchanged_required",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX and static assets must remain unchanged during production drift monitoring.",
        ));
    }

    let rollback_ready = bool_value(payload.get("python_backend_rollback_package_ready"), false)
        && bool_value(payload.get("rollback_test_passed"), false)
        && str_value(payload.get("rollback_path"), "").len() > 0;
    if require_rollback_package && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_rollback_required",
            Some("python_backend_rollback_package_ready".to_string()),
            "Rollback package, rollback path, and rollback test must remain available during production drift monitoring.",
        ));
    }

    let tests_passed = bool_value(payload.get("server_cargo_tests_passed"), false)
        && bool_value(payload.get("self_test_passed"), false)
        && bool_value(payload.get("production_healthcheck_passed"), false)
        && bool_value(payload.get("post_retirement_healthcheck_passed"), false)
        && bool_value(payload.get("steady_state_healthcheck_passed"), false)
        && bool_value(payload.get("drift_monitor_healthcheck_passed"), false);
    if require_server_tests && !tests_passed {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_tests_required",
            Some("server_cargo_tests_passed".to_string()),
            "Server cargo, self-test, production, post-retirement, steady-state, and drift-monitor healthchecks must pass.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_full_rust_backend_drift_monitor_ack"), false) || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_operator_ack_required",
            Some("operator_full_rust_backend_drift_monitor_ack".to_string()),
            "Operator acknowledgement is required for production drift monitoring verification.",
        ));
    }

    let gates_ready = allow_monitor && monitor_pilot && monitor_mode == "monitor_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_drift_monitor_gates_not_enabled",
            Some("rust_core".to_string()),
            "Production drift monitor gates are not fully enabled.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_steady_state || steady_state_ready)
        && (!require_runtime_health || rust_runtime_ready)
        && (!require_no_drift || python_drift_absent)
        && (!require_webui_unchanged || webui_unchanged)
        && (!require_rollback_package || rollback_ready)
        && (!require_server_tests || tests_passed)
        && (!require_operator_ack || operator_ack)
        && shadow_age <= max_shadow_age;

    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_production_drift_monitor_healthy"
    } else if steady_state_ready && rust_runtime_ready {
        "full_rust_backend_production_drift_monitor_review"
    } else {
        "full_rust_backend_production_drift_monitor_blocked"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("steady_state_status".to_string(), json!(steady_state_status));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_production_drift_monitor"));
    map.insert("status".to_string(), json!(status));
    map.insert("drift_monitor_id".to_string(), json!(drift_monitor_id(&Value::Object(seed))));
    map.insert("full_rust_backend".to_string(), json!(ready));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(ready));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(ready && rust_runtime_ready));
    map.insert("api_traffic_switched_to_rust".to_string(), json!(bool_value(payload.get("api_traffic_switched_to_rust"), false)));
    map.insert("python_backend_removed".to_string(), json!(ready && python_drift_absent));
    map.insert("python_backend_retired".to_string(), json!(ready && python_drift_absent));
    map.insert("python_drift_absent".to_string(), json!(python_drift_absent));
    map.insert("python_backend_drift_detected".to_string(), json!(!python_drift_absent));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("server_tests_passed".to_string(), json!(tests_passed));
    map.insert("steady_state_guard_ready".to_string(), json!(steady_state_ready));
    map.insert("drift_check_count".to_string(), json!(drift_check_count));
    map.insert("python_backend_process_count".to_string(), json!(python_process_count));
    map.insert("monitor_allowed".to_string(), json!(ready));
    map.insert("webui_static_assets_preserved".to_string(), json!(bool_value(payload.get("webui_static_assets_preserved"), false)));
    map.insert("webui_static_asset_paths_unchanged".to_string(), json!(bool_value(payload.get("webui_static_asset_paths_unchanged"), false)));
    map.insert("non_mutating".to_string(), json!(true));
    map.insert("side_effects_allowed".to_string(), json!(false));
    map.insert("python_removal_executor_allowed".to_string(), json!(false));
    map.insert("rollback_execute_allowed".to_string(), json!(false));
    map.insert("steady_state_guard".to_string(), steady_state);

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        json!({
            "confirmation":"CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR",
            "shadow_age_seconds": 0,
            "full_rust_backend_steady_state_guard": {
                "status":"full_rust_backend_steady_state_verified",
                "full_rust_backend": true,
                "python_drift_absent": true
            },
            "rust_service_active": true,
            "rust_api_healthcheck_passed": true,
            "rust_unix_socket_active": true,
            "rust_service_runtime_authoritative": true,
            "api_traffic_switched_to_rust": true,
            "flask_routes_disabled": true,
            "python_backend_stopped_or_disabled": true,
            "python_backend_service_masked_or_disabled": true,
            "python_backend_unexpectedly_running": false,
            "flask_routes_reappeared": false,
            "api_traffic_routed_to_python": false,
            "python_backend_service_reenabled": false,
            "python_backend_process_count": 0,
            "drift_check_count": 1,
            "webui_ux_unchanged": true,
            "webui_static_asset_paths_unchanged": true,
            "webui_static_assets_preserved": true,
            "python_backend_rollback_package_ready": true,
            "rollback_path": "restore_python_backend_and_flask_routes",
            "rollback_test_passed": true,
            "server_cargo_tests_passed": true,
            "self_test_passed": true,
            "production_healthcheck_passed": true,
            "post_retirement_healthcheck_passed": true,
            "steady_state_healthcheck_passed": true,
            "drift_monitor_healthcheck_passed": true,
            "operator_full_rust_backend_drift_monitor_ack": true,
            "rust_core": {
                "full_rust_backend_production_drift_monitor_pilot": true,
                "allow_full_rust_backend_production_drift_monitor": true,
                "full_rust_backend_production_drift_monitor_mode": "monitor_only"
            }
        })
    }

    #[test]
    fn verifies_production_drift_monitor_when_gates_are_met() {
        let (result, errors, _warnings) = build_full_rust_backend_production_drift_monitor_payload(&ready_payload());
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_drift_monitor_healthy"));
        assert_eq!(result.get("full_rust_backend").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_drift_absent").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("side_effects_allowed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn defaults_to_blocked_when_gates_missing() {
        let (result, errors, warnings) = build_full_rust_backend_production_drift_monitor_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_drift_monitor_blocked"));
        assert!(!warnings.is_empty());
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = ready_payload();
        payload["execute"] = json!(true);
        let (_result, errors, _warnings) = build_full_rust_backend_production_drift_monitor_payload(&payload);
        assert!(errors.iter().any(|e| e.code == "full_rust_backend_production_drift_monitor_execute_not_implemented"));
    }
}
