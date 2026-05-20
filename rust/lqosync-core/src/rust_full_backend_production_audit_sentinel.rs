use crate::protocol::Diagnostic;
use crate::rust_full_backend_production_drift_monitor::build_full_rust_backend_production_drift_monitor_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_AUDIT_SENTINEL: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_AUDIT_SENTINEL";
const CONFIRM_DRIFT_MONITOR: &str = "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR";

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

fn audit_sentinel_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("fullrust-audit-{}", &digest[..16])
}

/// Build the v7.5 production audit sentinel for a fully migrated Rust backend.
///
/// This is a verification-only sentinel that runs after the production drift
/// monitor. It confirms that audit logs, transaction journal visibility,
/// rollback-preview visibility, WebUI preservation, and production drift health
/// continue to hold after Python retirement. It intentionally does not restart
/// services, delete files, write LibreQoS outputs, append audits, or execute
/// rollback.
pub fn build_full_rust_backend_production_audit_sentinel_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "sentinel"), "execute" | "repair" | "delete" | "disable" | "restart" | "switch" | "rollback" | "append" | "write");
    if requested_execute {
        errors.push(Diagnostic::error(
            "full_rust_backend_production_audit_sentinel_execute_not_implemented",
            Some("full_rust_backend_production_audit_sentinel".to_string()),
            "The production audit sentinel is verification-only. It does not mutate services, append audit logs, delete files, switch traffic, or execute rollback.",
        ));
    }

    let allow_sentinel = bool_value(config_value(payload, "allow_full_rust_backend_production_audit_sentinel"), false);
    let sentinel_pilot = bool_value(config_value(payload, "full_rust_backend_production_audit_sentinel_pilot"), false);
    let sentinel_mode = str_value(config_value(payload, "full_rust_backend_production_audit_sentinel_mode"), "sentinel_only");
    let require_drift_monitor = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_drift_monitor"), true);
    let require_audit_trail = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_audit_trail"), true);
    let require_journal_visibility = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_journal_visibility"), true);
    let require_rollback_visibility = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_rollback_visibility"), true);
    let require_webui_unchanged = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_webui_unchanged"), true);
    let require_server_tests = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_server_tests"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_manual_confirmation"), true);
    let require_operator_ack = bool_value(config_value(payload, "full_rust_backend_audit_sentinel_require_operator_ack"), true);
    let max_shadow_age = number_value(config_value(payload, "full_rust_backend_audit_sentinel_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_AUDIT_SENTINEL;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_confirmation_required",
            Some("confirmation".to_string()),
            "Production audit sentinel requires CONFIRM_FULL_RUST_BACKEND_PRODUCTION_AUDIT_SENTINEL before it can report healthy.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_stale",
            Some("shadow_age_seconds".to_string()),
            "Production audit sentinel observations are older than the configured maximum age.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let drift_value = first_object(payload, &[
        "full_rust_backend_production_drift_monitor",
        "full_rust_backend_production_drift_monitor_contract",
        "rust_full_backend_production_drift_monitor",
    ]).cloned();

    let (drift_monitor, drift_errors, mut drift_warnings) = match drift_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("full_rust_backend_production_drift_monitor_confirmation"),
                    CONFIRM_DRIFT_MONITOR,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_full_rust_backend_production_drift_monitor_payload(&nested_payload)
        }
    };
    warnings.append(&mut drift_warnings);

    let drift_status = drift_monitor.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let drift_ready = drift_errors.is_empty()
        && drift_status == "full_rust_backend_production_drift_monitor_healthy"
        && drift_monitor.get("full_rust_backend").and_then(Value::as_bool).unwrap_or(false)
        && drift_monitor.get("python_drift_absent").and_then(Value::as_bool).unwrap_or(false);
    if require_drift_monitor && !drift_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_drift_monitor_not_ready",
            Some("full_rust_backend_production_drift_monitor".to_string()),
            "Production drift monitor has not verified healthy; audit sentinel remains blocked or review-only.",
        ));
    }

    let audit_event_count = number_value(payload.get("audit_event_count"), 0);
    let audit_trail_ready = bool_value(payload.get("audit_log_available"), false)
        && bool_value(payload.get("audit_log_readable"), false)
        && bool_value(payload.get("audit_log_redaction_verified"), false)
        && bool_value(payload.get("audit_append_rehearsal_passed"), false)
        && audit_event_count > 0;
    if require_audit_trail && !audit_trail_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_audit_trail_required",
            Some("audit_log_available".to_string()),
            "Audit log availability, readability, redaction, append rehearsal, and at least one audit event are required.",
        ));
    }

    let journal_entry_count = number_value(payload.get("transaction_journal_entry_count"), 0);
    let journal_ready = bool_value(payload.get("transaction_journal_readable"), false)
        && bool_value(payload.get("transaction_journal_preview_passed"), false)
        && bool_value(payload.get("transaction_journal_redaction_verified"), false)
        && journal_entry_count > 0;
    if require_journal_visibility && !journal_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_journal_visibility_required",
            Some("transaction_journal_readable".to_string()),
            "Transaction journal readability, preview, redaction, and at least one visible journal entry are required.",
        ));
    }

    let rollback_ready = bool_value(payload.get("rollback_manifest_preview_available"), false)
        && bool_value(payload.get("rollback_from_journal_preview_available"), false)
        && bool_value(payload.get("rollback_test_passed"), false)
        && bool_value(payload.get("python_backend_rollback_package_ready"), false)
        && str_value(payload.get("rollback_path"), "").len() > 0;
    if require_rollback_visibility && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_rollback_visibility_required",
            Some("rollback_manifest_preview_available".to_string()),
            "Rollback manifest preview, rollback-from-journal preview, rollback test, package, and path must remain available.",
        ));
    }

    let webui_unchanged = bool_value(payload.get("webui_ux_unchanged"), false)
        && bool_value(payload.get("webui_static_asset_paths_unchanged"), false)
        && bool_value(payload.get("webui_static_assets_preserved"), false);
    if require_webui_unchanged && !webui_unchanged {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_webui_unchanged_required",
            Some("webui_ux_unchanged".to_string()),
            "WebUI/UX and static assets must remain unchanged during audit sentinel verification.",
        ));
    }

    let tests_passed = bool_value(payload.get("server_cargo_tests_passed"), false)
        && bool_value(payload.get("self_test_passed"), false)
        && bool_value(payload.get("production_healthcheck_passed"), false)
        && bool_value(payload.get("post_retirement_healthcheck_passed"), false)
        && bool_value(payload.get("steady_state_healthcheck_passed"), false)
        && bool_value(payload.get("drift_monitor_healthcheck_passed"), false)
        && bool_value(payload.get("audit_sentinel_healthcheck_passed"), false);
    if require_server_tests && !tests_passed {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_tests_required",
            Some("server_cargo_tests_passed".to_string()),
            "Server cargo, self-test, production, post-retirement, steady-state, drift-monitor, and audit-sentinel healthchecks must pass.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_full_rust_backend_audit_sentinel_ack"), false) || bool_value(payload.get("operator_acknowledged"), false);
    if require_operator_ack && !operator_ack {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_operator_ack_required",
            Some("operator_full_rust_backend_audit_sentinel_ack".to_string()),
            "Operator acknowledgement is required for production audit sentinel verification.",
        ));
    }

    let gates_ready = allow_sentinel && sentinel_pilot && sentinel_mode == "sentinel_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "full_rust_backend_audit_sentinel_gates_not_enabled",
            Some("rust_core".to_string()),
            "Production audit sentinel gates are not fully enabled.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_drift_monitor || drift_ready)
        && (!require_audit_trail || audit_trail_ready)
        && (!require_journal_visibility || journal_ready)
        && (!require_rollback_visibility || rollback_ready)
        && (!require_webui_unchanged || webui_unchanged)
        && (!require_server_tests || tests_passed)
        && (!require_operator_ack || operator_ack)
        && shadow_age <= max_shadow_age;

    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "full_rust_backend_production_audit_sentinel_healthy"
    } else if drift_ready {
        "full_rust_backend_production_audit_sentinel_review"
    } else {
        "full_rust_backend_production_audit_sentinel_blocked"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("drift_status".to_string(), json!(drift_status));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("full_rust_backend_production_audit_sentinel"));
    map.insert("status".to_string(), json!(status));
    map.insert("audit_sentinel_id".to_string(), json!(audit_sentinel_id(&Value::Object(seed))));
    map.insert("full_rust_backend".to_string(), json!(ready));
    map.insert("full_rust_backend_production_enabled".to_string(), json!(ready));
    map.insert("rust_service_runtime_authoritative".to_string(), json!(ready && drift_ready));
    map.insert("python_backend_removed".to_string(), json!(ready && drift_monitor.get("python_backend_removed").and_then(Value::as_bool).unwrap_or(false)));
    map.insert("python_backend_retired".to_string(), json!(ready && drift_monitor.get("python_backend_retired").and_then(Value::as_bool).unwrap_or(false)));
    map.insert("python_drift_absent".to_string(), json!(drift_monitor.get("python_drift_absent").and_then(Value::as_bool).unwrap_or(false)));
    map.insert("audit_trail_ready".to_string(), json!(audit_trail_ready));
    map.insert("journal_visibility_ready".to_string(), json!(journal_ready));
    map.insert("rollback_visibility_ready".to_string(), json!(rollback_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(webui_unchanged));
    map.insert("server_tests_passed".to_string(), json!(tests_passed));
    map.insert("audit_event_count".to_string(), json!(audit_event_count));
    map.insert("transaction_journal_entry_count".to_string(), json!(journal_entry_count));
    map.insert("audit_sentinel_allowed".to_string(), json!(ready));
    map.insert("non_mutating".to_string(), json!(true));
    map.insert("side_effects_allowed".to_string(), json!(false));
    map.insert("audit_append_allowed".to_string(), json!(false));
    map.insert("rollback_execute_allowed".to_string(), json!(false));
    map.insert("drift_monitor".to_string(), drift_monitor);

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        json!({
            "confirmation":"CONFIRM_FULL_RUST_BACKEND_PRODUCTION_AUDIT_SENTINEL",
            "shadow_age_seconds": 0,
            "full_rust_backend_production_drift_monitor": {
                "status":"full_rust_backend_production_drift_monitor_healthy",
                "full_rust_backend": true,
                "python_drift_absent": true,
                "python_backend_removed": true,
                "python_backend_retired": true
            },
            "audit_log_available": true,
            "audit_log_readable": true,
            "audit_log_redaction_verified": true,
            "audit_append_rehearsal_passed": true,
            "audit_event_count": 1,
            "transaction_journal_readable": true,
            "transaction_journal_preview_passed": true,
            "transaction_journal_redaction_verified": true,
            "transaction_journal_entry_count": 1,
            "rollback_manifest_preview_available": true,
            "rollback_from_journal_preview_available": true,
            "python_backend_rollback_package_ready": true,
            "rollback_path": "restore_python_backend_and_flask_routes",
            "rollback_test_passed": true,
            "webui_ux_unchanged": true,
            "webui_static_asset_paths_unchanged": true,
            "webui_static_assets_preserved": true,
            "server_cargo_tests_passed": true,
            "self_test_passed": true,
            "production_healthcheck_passed": true,
            "post_retirement_healthcheck_passed": true,
            "steady_state_healthcheck_passed": true,
            "drift_monitor_healthcheck_passed": true,
            "audit_sentinel_healthcheck_passed": true,
            "operator_full_rust_backend_audit_sentinel_ack": true,
            "rust_core": {
                "full_rust_backend_production_audit_sentinel_pilot": true,
                "allow_full_rust_backend_production_audit_sentinel": true,
                "full_rust_backend_production_audit_sentinel_mode": "sentinel_only"
            }
        })
    }

    #[test]
    fn verifies_production_audit_sentinel_when_gates_are_met() {
        let (result, errors, _warnings) = build_full_rust_backend_production_audit_sentinel_payload(&ready_payload());
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_audit_sentinel_healthy"));
        assert_eq!(result.get("full_rust_backend").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("audit_trail_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("side_effects_allowed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn defaults_to_blocked_when_gates_missing() {
        let (result, errors, warnings) = build_full_rust_backend_production_audit_sentinel_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("full_rust_backend_production_audit_sentinel_blocked"));
        assert!(!warnings.is_empty());
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = ready_payload();
        payload["execute"] = json!(true);
        let (_result, errors, _warnings) = build_full_rust_backend_production_audit_sentinel_payload(&payload);
        assert!(errors.iter().any(|e| e.code == "full_rust_backend_production_audit_sentinel_execute_not_implemented"));
    }
}
