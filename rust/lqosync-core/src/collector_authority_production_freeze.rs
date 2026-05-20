use crate::collector_authority_promotion_cutover::build_collector_authority_promotion_cutover_ledger_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_PRODUCTION_FREEZE_GATE: &str = "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE";
const CONFIRM_CUTOVER_LEDGER: &str = "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER";

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

fn freeze_gate_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("capfreeze-{}", &digest[..16])
}

/// Build a non-mutating production freeze gate for future Rust collector authority.
///
/// v4.9 is the final pre-production guard before any future Rust authority switch
/// contract. It can report that all pre-switch gates are frozen, but it does not
/// switch production authority, disable Python fallback, run cleanup, write files,
/// or apply LibreQoS.
pub fn build_collector_authority_production_freeze_gate_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "freeze"), "execute" | "commit" | "switch" | "promote" | "authority" | "apply" | "production" | "cutover");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_production_freeze_execute_not_implemented",
            Some("collector_authority_production_freeze_gate".to_string()),
            "This release only builds a production freeze gate. It does not switch Rust collector authority, drive cleanup, write files, or apply LibreQoS.",
        ));
    }

    let allow_freeze = bool_value(config_value(payload, "allow_collector_authority_production_freeze_gate"), false);
    let freeze_pilot = bool_value(config_value(payload, "collector_authority_production_freeze_gate_pilot"), false);
    let freeze_mode = str_value(config_value(payload, "collector_authority_production_freeze_mode"), "freeze_only");
    let require_cutover_ledger = bool_value(config_value(payload, "collector_authority_production_freeze_require_cutover_ledger"), true);
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_production_freeze_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "collector_authority_production_freeze_require_manual_confirmation"), true);
    let require_no_side_effects = bool_value(config_value(payload, "collector_authority_production_freeze_require_no_cleanup_apply"), true);
    let require_rollback_path = bool_value(config_value(payload, "collector_authority_production_freeze_require_rollback_path"), true);
    let require_maintenance_window = bool_value(config_value(payload, "collector_authority_production_freeze_require_maintenance_window"), true);
    let require_operator_ack = bool_value(config_value(payload, "collector_authority_production_freeze_require_operator_ack"), true);
    let max_shadow_age = number_value(config_value(payload, "collector_authority_production_freeze_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_PRODUCTION_FREEZE_GATE;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_confirmation_required",
            Some("confirmation".to_string()),
            "Production freeze gate requires CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_production_freeze_requires_python_fallback",
            Some("rust_core.collector_authority_production_freeze_require_python_fallback".to_string()),
            "Production freeze gate still requires Python collector fallback in this release. Actual fallback removal belongs to a later full-Rust production backend release.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow collector data is older than the configured maximum age; production freeze remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let cutover_value = first_object(payload, &[
        "collector_authority_promotion_cutover_ledger",
        "promotion_cutover_ledger",
        "collector_authority_cutover_ledger",
    ]).cloned();

    let (cutover_ledger, cutover_errors, mut cutover_warnings) = match cutover_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let cutover_confirmation = str_value(
                    payload.get("collector_authority_promotion_cutover_confirmation"),
                    CONFIRM_CUTOVER_LEDGER,
                );
                obj.insert("confirmation".to_string(), json!(cutover_confirmation));
            }
            build_collector_authority_promotion_cutover_ledger_payload(&nested_payload)
        }
    };
    warnings.append(&mut cutover_warnings);

    if !cutover_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_cutover_not_clean",
            Some("collector_authority_promotion_cutover_ledger".to_string()),
            "Cutover ledger returned errors; production freeze remains shadow-only.",
        ));
    }

    let cutover_status = cutover_ledger.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let cutover_ready = cutover_errors.is_empty()
        && cutover_status == "collector_authority_promotion_cutover_ledger_ready"
        && cutover_ledger.get("cutover_ledger_ready").and_then(Value::as_bool).unwrap_or(false)
        && cutover_ledger.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && cutover_ledger.get("python_collector_fallback_required").and_then(Value::as_bool).unwrap_or(true);

    if require_cutover_ledger && !cutover_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_cutover_not_ready",
            Some("collector_authority_promotion_cutover_ledger".to_string()),
            "Collector authority cutover ledger has not passed; production freeze remains shadow-only or under review.",
        ));
    }

    let cleanup_attempted = bool_value(payload.get("cleanup_attempted"), false)
        || bool_value(cutover_ledger.get("cleanup_attempted"), false);
    let apply_attempted = bool_value(payload.get("apply_attempted"), false)
        || bool_value(cutover_ledger.get("apply_attempted"), false);
    let write_attempted = bool_value(payload.get("write_attempted"), false)
        || bool_value(cutover_ledger.get("write_attempted"), false);
    let authority_switched = bool_value(payload.get("production_collector_authority_switched"), false)
        || bool_value(cutover_ledger.get("production_collector_authority_switched"), false);
    let side_effect_free = !cleanup_attempted && !apply_attempted && !write_attempted && !authority_switched;

    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "collector_authority_production_freeze_side_effect_detected",
            Some("collector_authority_production_freeze_gate".to_string()),
            "Production freeze detected cleanup/apply/write/authority side effects, which are forbidden in this release.",
        ));
    }

    let rollback_path = payload
        .get("rollback_path")
        .and_then(Value::as_str)
        .or_else(|| cutover_ledger.get("rollback_path").and_then(Value::as_str))
        .unwrap_or("python_fallback_revert");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_rollback_path_required",
            Some("rollback_path".to_string()),
            "Production freeze requires an explicit rollback path before it can report ready.",
        ));
    }

    let maintenance_window = str_value(payload.get("maintenance_window"), "");
    let maintenance_window_ready = !require_maintenance_window || !maintenance_window.trim().is_empty();
    if require_maintenance_window && !maintenance_window_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_maintenance_window_required",
            Some("maintenance_window".to_string()),
            "Production freeze requires an explicit maintenance window before it can report ready.",
        ));
    }

    let operator_ack = bool_value(payload.get("operator_acknowledged"), false);
    let operator_ack_ready = !require_operator_ack || operator_ack;
    if require_operator_ack && !operator_ack_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_operator_ack_required",
            Some("operator_acknowledged".to_string()),
            "Production freeze requires explicit operator acknowledgment before it can report ready.",
        ));
    }

    let gates_ready = allow_freeze && freeze_pilot && freeze_mode == "freeze_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_production_freeze_gates_not_enabled",
            Some("rust_core".to_string()),
            "Production freeze gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_cutover_ledger || cutover_ready)
        && shadow_age <= max_shadow_age
        && side_effect_free
        && require_python_fallback
        && rollback_ready
        && maintenance_window_ready
        && operator_ack_ready;

    let review = errors.is_empty() && cutover_ready && side_effect_free && rollback_ready;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "collector_authority_production_freeze_gate_ready"
    } else if review {
        "collector_authority_production_freeze_gate_review"
    } else {
        "collector_authority_production_freeze_gate_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("cutover_status".to_string(), json!(cutover_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));
    seed.insert("maintenance_window_ready".to_string(), json!(maintenance_window_ready));

    let mut freeze_steps = Vec::new();
    let mut s1 = Map::new();
    s1.insert("step".to_string(), json!(1));
    s1.insert("name".to_string(), json!("freeze_cutover_inputs"));
    s1.insert("mutating".to_string(), json!(false));
    freeze_steps.push(Value::Object(s1));
    let mut s2 = Map::new();
    s2.insert("step".to_string(), json!(2));
    s2.insert("name".to_string(), json!("verify_python_fallback_still_enabled"));
    s2.insert("mutating".to_string(), json!(false));
    freeze_steps.push(Value::Object(s2));
    let mut s3 = Map::new();
    s3.insert("step".to_string(), json!(3));
    s3.insert("name".to_string(), json!("defer_authority_switch_to_v5_contract"));
    s3.insert("mutating".to_string(), json!(false));
    freeze_steps.push(Value::Object(s3));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("collector_authority_production_freeze_gate"));
    map.insert("status".to_string(), json!(status));
    map.insert("production_freeze_gate_id".to_string(), json!(freeze_gate_id(&Value::Object(seed))));
    map.insert("collector_authority".to_string(), json!("python_authoritative"));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("production_freeze_gate_only".to_string(), json!(true));
    map.insert("production_freeze_ready".to_string(), json!(ready));
    map.insert("collector_authority_production_switch_supported".to_string(), json!(false));
    map.insert("collector_authority_production_switch_executed".to_string(), json!(false));
    map.insert("production_collector_authority_switched".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_collector_fallback_required".to_string(), json!(true));
    map.insert("rust_can_drive_cleanup".to_string(), json!(false));
    map.insert("rust_can_drive_apply".to_string(), json!(false));
    map.insert("rust_can_write_generated_files".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("rollback_path_required".to_string(), json!(require_rollback_path));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("maintenance_window_required".to_string(), json!(require_maintenance_window));
    map.insert("maintenance_window".to_string(), json!(maintenance_window));
    map.insert("maintenance_window_ready".to_string(), json!(maintenance_window_ready));
    map.insert("operator_ack_required".to_string(), json!(require_operator_ack));
    map.insert("operator_acknowledged".to_string(), json!(operator_ack));
    map.insert("operator_ack_ready".to_string(), json!(operator_ack_ready));
    map.insert("manual_confirmation_required".to_string(), json!(require_manual_confirmation));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("cutover_ledger_status".to_string(), json!(cutover_status));
    map.insert("cutover_ledger_ready".to_string(), json!(cutover_ready));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("side_effect_free".to_string(), json!(side_effect_free));
    map.insert("freeze_steps".to_string(), Value::Array(freeze_steps));
    map.insert("next_stage".to_string(), json!("v5_collector_authority_production_switch_contract"));
    map.insert("note".to_string(), json!("v4.9 builds the final non-mutating production freeze gate before a future v5 Rust collector authority switch contract. It does not remove Python or switch production authority."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_PRODUCTION_FREEZE_GATE));
        root.insert("shadow_age_seconds".to_string(), json!(20));
        root.insert("maintenance_window".to_string(), json!("2026-05-20T23:00:00+08:00/PT30M"));
        root.insert("operator_acknowledged".to_string(), json!(true));
        root.insert("rollback_path".to_string(), json!("python_fallback_revert"));

        let mut rc = Map::new();
        rc.insert("collector_authority_production_freeze_gate_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_production_freeze_gate".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_mode".to_string(), json!("freeze_only"));
        rc.insert("collector_authority_production_freeze_require_cutover_ledger".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_python_fallback".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_manual_confirmation".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_no_cleanup_apply".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_rollback_path".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_maintenance_window".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_require_operator_ack".to_string(), json!(true));
        rc.insert("collector_authority_production_freeze_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut ledger = Map::new();
        ledger.insert("status".to_string(), json!("collector_authority_promotion_cutover_ledger_ready"));
        ledger.insert("cutover_ledger_ready".to_string(), json!(true));
        ledger.insert("python_collector_fallback_required".to_string(), json!(true));
        ledger.insert("production_collector_authority_switched".to_string(), json!(false));
        ledger.insert("rollback_path".to_string(), json!("python_fallback_revert"));
        ledger.insert("cleanup_attempted".to_string(), json!(false));
        ledger.insert("apply_attempted".to_string(), json!(false));
        ledger.insert("write_attempted".to_string(), json!(false));
        root.insert("collector_authority_promotion_cutover_ledger".to_string(), Value::Object(ledger));
        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_production_freeze_gate() {
        let (result, errors, _warnings) = build_collector_authority_production_freeze_gate_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_production_freeze_gate_shadow_only"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_backend_removable").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_collector_authority_production_freeze_gate_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_freeze_gate_without_switching_authority() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_collector_authority_production_freeze_gate_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_production_freeze_gate_ready"));
        assert_eq!(result.get("production_freeze_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("collector_authority_production_switch_executed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_backend_removable").and_then(Value::as_bool), Some(false));
    }
}
