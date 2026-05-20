use crate::collector_authority_promotion_commit::build_collector_authority_promotion_commit_plan_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_CUTOVER_LEDGER: &str = "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER";
const CONFIRM_COMMIT_PLAN: &str = "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN";

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

fn ledger_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("capledger-{}", &digest[..16])
}

/// Build a non-mutating cutover ledger for future collector-authority promotion.
///
/// v4.8 is still a ledger/guard bridge. It can prove that the v4.7 commit plan
/// is ready and can produce an auditable cutover intent ledger, but it does not
/// promote Rust collectors, drive cleanup, write files, apply LibreQoS, or disable
/// the Python collector fallback.
pub fn build_collector_authority_promotion_cutover_ledger_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "ledger"), "execute" | "commit" | "switch" | "promote" | "authority" | "apply" | "production" | "cutover");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_promotion_cutover_not_implemented",
            Some("collector_authority_promotion_cutover_ledger".to_string()),
            "This release only builds a collector authority promotion cutover ledger. It does not promote Rust collectors, drive cleanup, write files, or apply LibreQoS.",
        ));
    }

    let allow_ledger = bool_value(config_value(payload, "allow_collector_authority_promotion_cutover_ledger"), false);
    let ledger_pilot = bool_value(config_value(payload, "collector_authority_promotion_cutover_ledger_pilot"), false);
    let ledger_mode = str_value(config_value(payload, "collector_authority_promotion_cutover_mode"), "ledger_only");
    let require_commit_plan = bool_value(config_value(payload, "collector_authority_promotion_cutover_require_commit_plan"), true);
    let require_python_fallback = bool_value(config_value(payload, "collector_authority_promotion_cutover_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "collector_authority_promotion_cutover_require_manual_confirmation"), true);
    let require_no_side_effects = bool_value(config_value(payload, "collector_authority_promotion_cutover_require_no_cleanup_apply"), true);
    let require_rollback_path = bool_value(config_value(payload, "collector_authority_promotion_cutover_require_rollback_path"), true);
    let max_shadow_age = number_value(config_value(payload, "collector_authority_promotion_cutover_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_CUTOVER_LEDGER;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_confirmation_required",
            Some("confirmation".to_string()),
            "Collector authority promotion cutover ledger requires CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "collector_authority_promotion_cutover_requires_python_fallback",
            Some("rust_core.collector_authority_promotion_cutover_require_python_fallback".to_string()),
            "Collector authority promotion cutover ledger requires Python collector fallback in this release.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow collector data is older than the configured maximum age; cutover ledger remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let commit_value = first_object(payload, &[
        "collector_authority_promotion_commit_plan",
        "promotion_commit_plan",
        "collector_authority_promotion_commit_report",
    ]).cloned();

    let (commit_plan, commit_errors, mut commit_warnings) = match commit_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let commit_confirmation = str_value(
                    payload.get("collector_authority_promotion_commit_confirmation"),
                    CONFIRM_COMMIT_PLAN,
                );
                obj.insert("confirmation".to_string(), json!(commit_confirmation));
            }
            build_collector_authority_promotion_commit_plan_payload(&nested_payload)
        }
    };
    warnings.append(&mut commit_warnings);

    if !commit_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_commit_plan_not_clean",
            Some("collector_authority_promotion_commit_plan".to_string()),
            "Promotion commit plan returned errors; cutover ledger remains shadow-only.",
        ));
    }

    let commit_status = commit_plan.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let commit_ready = commit_errors.is_empty()
        && commit_status == "collector_authority_promotion_commit_plan_ready"
        && commit_plan.get("promotion_commit_plan_ready").and_then(Value::as_bool).unwrap_or(false)
        && commit_plan.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && commit_plan.get("python_collector_fallback_required").and_then(Value::as_bool).unwrap_or(true);

    if require_commit_plan && !commit_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_commit_plan_not_ready",
            Some("collector_authority_promotion_commit_plan".to_string()),
            "Collector authority promotion commit plan has not passed; cutover ledger remains shadow-only or under review.",
        ));
    }

    let cleanup_attempted = bool_value(payload.get("cleanup_attempted"), false)
        || bool_value(commit_plan.get("cleanup_attempted"), false);
    let apply_attempted = bool_value(payload.get("apply_attempted"), false)
        || bool_value(commit_plan.get("apply_attempted"), false);
    let write_attempted = bool_value(payload.get("write_attempted"), false)
        || bool_value(commit_plan.get("write_attempted"), false);
    let authority_switched = bool_value(payload.get("production_collector_authority_switched"), false)
        || bool_value(commit_plan.get("production_collector_authority_switched"), false);
    let side_effect_free = !cleanup_attempted && !apply_attempted && !write_attempted && !authority_switched;

    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "collector_authority_promotion_cutover_side_effect_detected",
            Some("collector_authority_promotion_cutover_ledger".to_string()),
            "Cutover ledger detected cleanup/apply/write/authority side effects, which are forbidden in this release.",
        ));
    }

    let rollback_path = str_value(payload.get("rollback_path"), "python_fallback_revert");
    let rollback_ready = !require_rollback_path || !rollback_path.trim().is_empty();
    if require_rollback_path && !rollback_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_rollback_path_required",
            Some("rollback_path".to_string()),
            "Cutover ledger requires an explicit rollback path before it can report ready.",
        ));
    }

    let gates_ready = allow_ledger && ledger_pilot && ledger_mode == "ledger_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "collector_authority_promotion_cutover_gates_not_enabled",
            Some("rust_core".to_string()),
            "Collector authority promotion cutover ledger gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_commit_plan || commit_ready)
        && shadow_age <= max_shadow_age
        && side_effect_free
        && require_python_fallback
        && rollback_ready;

    let review = errors.is_empty() && commit_ready && side_effect_free && rollback_ready;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "collector_authority_promotion_cutover_ledger_ready"
    } else if review {
        "collector_authority_promotion_cutover_ledger_review"
    } else {
        "collector_authority_promotion_cutover_ledger_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("commit_status".to_string(), json!(commit_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut planned = Vec::new();
    let mut step1 = Map::new();
    step1.insert("step".to_string(), json!(1));
    step1.insert("name".to_string(), json!("record_promotion_intent"));
    step1.insert("mutating".to_string(), json!(false));
    planned.push(Value::Object(step1));
    let mut step2 = Map::new();
    step2.insert("step".to_string(), json!(2));
    step2.insert("name".to_string(), json!("keep_python_fallback_enabled"));
    step2.insert("mutating".to_string(), json!(false));
    planned.push(Value::Object(step2));
    let mut step3 = Map::new();
    step3.insert("step".to_string(), json!(3));
    step3.insert("name".to_string(), json!("defer_authority_flip_to_future_release"));
    step3.insert("mutating".to_string(), json!(false));
    planned.push(Value::Object(step3));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("collector_authority_promotion_cutover_ledger"));
    map.insert("status".to_string(), json!(status));
    map.insert("cutover_ledger_id".to_string(), json!(ledger_id(&Value::Object(seed))));
    map.insert("collector_authority".to_string(), json!("python_authoritative"));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("cutover_ledger_only".to_string(), json!(true));
    map.insert("cutover_ledger_ready".to_string(), json!(ready));
    map.insert("collector_authority_promotion_supported".to_string(), json!(false));
    map.insert("collector_authority_promotion_executed".to_string(), json!(false));
    map.insert("production_collector_authority_switched".to_string(), json!(false));
    map.insert("rust_can_drive_cleanup".to_string(), json!(false));
    map.insert("rust_can_drive_apply".to_string(), json!(false));
    map.insert("rust_can_write_generated_files".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("python_collector_fallback_required".to_string(), json!(true));
    map.insert("rollback_path_required".to_string(), json!(require_rollback_path));
    map.insert("rollback_path".to_string(), json!(rollback_path));
    map.insert("rollback_ready".to_string(), json!(rollback_ready));
    map.insert("manual_confirmation_required".to_string(), json!(require_manual_confirmation));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("promotion_commit_plan_status".to_string(), json!(commit_status));
    map.insert("promotion_commit_plan_ready".to_string(), json!(commit_ready));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("side_effect_free".to_string(), json!(side_effect_free));
    map.insert("planned_cutover_steps".to_string(), Value::Array(planned));
    map.insert("connection_attempt_count".to_string(), json!(0));
    map.insert("authentication_attempt_count".to_string(), json!(0));
    map.insert("api_sentence_write_count".to_string(), json!(0));
    map.insert("api_reply_read_count".to_string(), json!(0));
    map.insert("note".to_string(), json!("v4.8 builds a non-mutating collector authority promotion cutover ledger after the commit plan. It does not promote Rust collectors or transfer cleanup/apply authority."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_payload() -> Value {
        let mut rc = Map::new();
        rc.insert("allow_rust_collector_authority".to_string(), json!(true));
        rc.insert("rust_collector_authority_pilot".to_string(), json!(true));
        rc.insert("allow_rust_routeros_live_read_adapter".to_string(), json!(true));
        rc.insert("routeros_live_read_adapter_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_dry_run_bundle".to_string(), json!(true));
        rc.insert("collector_authority_dry_run_bundle_pilot".to_string(), json!(true));
        rc.insert("run_cycle_rust_shadow_report_enabled".to_string(), json!(true));
        rc.insert("run_cycle_rust_shadow_report_pilot".to_string(), json!(true));
        rc.insert("collector_authority_activation_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_activation".to_string(), json!(true));
        rc.insert("collector_authority_activation_mode".to_string(), json!("shadow_pilot"));
        rc.insert("collector_authority_min_shadow_cycles".to_string(), json!(3));
        rc.insert("collector_authority_runtime_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_runtime_contract".to_string(), json!(true));
        rc.insert("collector_authority_runtime_mode".to_string(), json!("contract_only"));
        rc.insert("collector_authority_switch_rehearsal_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_switch_rehearsal".to_string(), json!(true));
        rc.insert("collector_authority_switch_mode".to_string(), json!("rehearsal_only"));
        rc.insert("collector_authority_pilot_execution_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_pilot_execution_contract".to_string(), json!(true));
        rc.insert("collector_authority_pilot_execution_mode".to_string(), json!("contract_only"));
        rc.insert("collector_authority_pilot_result_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_pilot_result_evaluation".to_string(), json!(true));
        rc.insert("collector_authority_pilot_result_mode".to_string(), json!("evaluate_only"));
        rc.insert("collector_authority_promotion_readiness_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_promotion_readiness".to_string(), json!(true));
        rc.insert("collector_authority_promotion_readiness_mode".to_string(), json!("readiness_only"));
        rc.insert("collector_authority_promotion_execution_rehearsal_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_promotion_execution_rehearsal".to_string(), json!(true));
        rc.insert("collector_authority_promotion_execution_mode".to_string(), json!("rehearsal_only"));
        rc.insert("collector_authority_promotion_commit_plan_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_promotion_commit_plan".to_string(), json!(true));
        rc.insert("collector_authority_promotion_commit_mode".to_string(), json!("plan_only"));
        rc.insert("collector_authority_promotion_cutover_ledger_pilot".to_string(), json!(true));
        rc.insert("allow_collector_authority_promotion_cutover_ledger".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_mode".to_string(), json!("ledger_only"));
        rc.insert("collector_authority_promotion_cutover_require_commit_plan".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_require_python_fallback".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_require_manual_confirmation".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_require_no_cleanup_apply".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_require_rollback_path".to_string(), json!(true));
        rc.insert("collector_authority_promotion_cutover_max_shadow_age_seconds".to_string(), json!(900));

        let mut payload = Map::new();
        payload.insert("rust_core".to_string(), Value::Object(rc));
        payload.insert("sources".to_string(), json!(["pppoe"]));
        payload.insert("successful_shadow_cycles".to_string(), json!(3));
        payload.insert("shadow_age_seconds".to_string(), json!(30));
        payload.insert("confirmation".to_string(), json!(CONFIRM_CUTOVER_LEDGER));
        payload.insert("collector_authority_promotion_commit_confirmation".to_string(), json!(CONFIRM_COMMIT_PLAN));
        payload.insert("collector_authority_promotion_execution_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL"));
        payload.insert("collector_authority_promotion_readiness_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS"));
        payload.insert("collector_authority_pilot_execution_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION"));
        payload.insert("collector_authority_switch_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"));
        payload.insert("rollback_path".to_string(), json!("python_fallback_revert"));
        payload.insert("collector_parity".to_string(), json!({"parity_score":100.0,"verdict":"parity_pass"}));
        payload.insert("pilot_result".to_string(), json!({"status":"collector_authority_pilot_result_pass","error_count":0,"cleanup_attempted":false,"apply_attempted":false,"write_attempted":false}));
        Value::Object(payload)
    }

    #[test]
    fn defaults_to_shadow_only_cutover_ledger() {
        let (result, errors, _warnings) = build_collector_authority_promotion_cutover_ledger_payload(&json!({"sources":["pppoe"]}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_promotion_cutover_ledger_shadow_only"));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = base_payload();
        payload.as_object_mut().unwrap().insert("execute".to_string(), json!(true));
        let (_result, errors, _warnings) = build_collector_authority_promotion_cutover_ledger_payload(&payload);
        assert!(errors.iter().any(|e| e.code == "collector_authority_promotion_cutover_not_implemented"));
    }

    #[test]
    fn builds_ready_cutover_ledger_when_commit_plan_and_gates_are_ready() {
        let payload = base_payload();
        let (result, errors, _warnings) = build_collector_authority_promotion_cutover_ledger_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_promotion_cutover_ledger_ready"));
        assert_eq!(result.get("cutover_ledger_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("production_collector_authority_switched").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("safe_for_cleanup").and_then(Value::as_bool), Some(false));
    }
}
