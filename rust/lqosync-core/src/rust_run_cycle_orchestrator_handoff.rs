use crate::protocol::Diagnostic;
use crate::rust_backend_scheduler_handoff::build_rust_backend_scheduler_handoff_plan_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_RUN_CYCLE_ORCHESTRATOR_HANDOFF: &str = "CONFIRM_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT";
const CONFIRM_SCHEDULER_HANDOFF: &str = "CONFIRM_RUST_BACKEND_SCHEDULER_RUN_CYCLE_HANDOFF_PLAN";

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

fn handoff_id(seed: &Value) -> String {
    let text = serde_json::to_string(seed).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("rchandoff-{}", &digest[..16])
}

/// Build the Rust run_cycle orchestrator handoff contract while keeping Python authoritative.
///
/// v5.3 continues the full-Rust-backend track after the scheduler handoff plan. It
/// does not replace the Python run_cycle loop, does not remove Python, and does not
/// execute cleanup/apply/write operations. It only verifies the run_cycle orchestrator
/// contract prerequisites and returns a non-mutating handoff contract.
pub fn build_rust_run_cycle_orchestrator_handoff_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "commit" | "switch" | "remove-python" | "replace-run-cycle" | "production" | "cutover" | "authoritative"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_run_cycle_orchestrator_handoff_execute_not_implemented",
            Some("rust_run_cycle_orchestrator_handoff_contract".to_string()),
            "This release only builds a Rust run_cycle orchestrator handoff contract. It does not replace Python run_cycle or remove Python.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_rust_run_cycle_orchestrator_handoff_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_contract_pilot"), false);
    let handoff_mode = str_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_mode"), "contract_only");
    let require_scheduler_handoff = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_scheduler_handoff"), true);
    let require_python_fallback = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_manual_confirmation"), true);
    let require_run_cycle_shadow = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow"), true);
    let require_config_state_shadow = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_config_state_shadow"), true);
    let require_no_side_effects = bool_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_RUN_CYCLE_ORCHESTRATOR_HANDOFF;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_confirmation_required",
            Some("confirmation".to_string()),
            "Rust run_cycle orchestrator handoff requires CONFIRM_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "rust_run_cycle_orchestrator_handoff_requires_python_fallback",
            Some("rust_core.rust_run_cycle_orchestrator_handoff_require_python_fallback".to_string()),
            "v5.3 still requires Python run_cycle backend as fallback. Python removal belongs to a later authority execution phase.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; run_cycle orchestrator handoff remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let scheduler_handoff_value = first_object(payload, &[
        "rust_backend_scheduler_handoff_plan",
        "scheduler_handoff_plan",
        "rust_backend_scheduler_handoff",
    ]).cloned();

    let (scheduler_handoff, scheduler_errors, mut scheduler_warnings) = match scheduler_handoff_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let scheduler_confirmation = str_value(
                    payload.get("rust_backend_scheduler_handoff_confirmation"),
                    CONFIRM_SCHEDULER_HANDOFF,
                );
                obj.insert("confirmation".to_string(), json!(scheduler_confirmation));
            }
            build_rust_backend_scheduler_handoff_plan_payload(&nested_payload)
        }
    };
    warnings.append(&mut scheduler_warnings);

    if !scheduler_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_scheduler_not_clean",
            Some("rust_backend_scheduler_handoff_plan".to_string()),
            "Rust scheduler/run_cycle handoff plan returned errors; run_cycle orchestrator handoff remains shadow-only.",
        ));
    }

    let scheduler_status = scheduler_handoff.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let scheduler_ready = scheduler_errors.is_empty()
        && scheduler_status == "rust_backend_scheduler_handoff_plan_ready"
        && scheduler_handoff.get("rust_backend_scheduler_handoff_ready").and_then(Value::as_bool).unwrap_or(false)
        && scheduler_handoff.get("rust_scheduler_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && scheduler_handoff.get("rust_run_cycle_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && scheduler_handoff.get("python_backend_required").and_then(Value::as_bool).unwrap_or(true);

    if require_scheduler_handoff && !scheduler_ready {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_scheduler_not_ready",
            Some("rust_backend_scheduler_handoff_plan".to_string()),
            "Rust scheduler/run_cycle handoff plan has not passed; run_cycle orchestrator handoff remains shadow-only or under review.",
        ));
    }

    let run_cycle_manifest_ready = bool_value(payload.get("run_cycle_orchestrator_manifest_ready"), false);
    let run_cycle_shadow_ready = bool_value(payload.get("run_cycle_shadow_ready"), false);
    let run_cycle_shadow_count = number_value(payload.get("run_cycle_shadow_count"), 0);
    let run_cycle_ready = !require_run_cycle_shadow || (run_cycle_manifest_ready && run_cycle_shadow_ready && run_cycle_shadow_count > 0);
    if require_run_cycle_shadow && !run_cycle_ready {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_shadow_required",
            Some("run_cycle_shadow_ready".to_string()),
            "Rust run_cycle orchestrator handoff requires a manifest plus successful shadow cycles before it can report ready.",
        ));
    }

    let config_state_shadow_ready = bool_value(payload.get("config_state_shadow_ready"), false);
    let config_state_shadow_count = number_value(payload.get("config_state_shadow_count"), 0);
    let config_state_ready = !require_config_state_shadow || (config_state_shadow_ready && config_state_shadow_count > 0);
    if require_config_state_shadow && !config_state_ready {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_config_state_shadow_required",
            Some("config_state_shadow_ready".to_string()),
            "Rust run_cycle orchestrator handoff requires config/state shadow verification before it can report ready.",
        ));
    }

    let cleanup_attempted = bool_value(payload.get("cleanup_attempted"), false);
    let apply_attempted = bool_value(payload.get("apply_attempted"), false);
    let write_attempted = bool_value(payload.get("write_attempted"), false);
    let python_removed = bool_value(payload.get("python_backend_removed"), false);
    let run_cycle_switched = bool_value(payload.get("run_cycle_switched_to_rust"), false);
    let scheduler_switched = bool_value(payload.get("scheduler_switched_to_rust"), false);
    let side_effect_free = !cleanup_attempted && !apply_attempted && !write_attempted && !python_removed && !run_cycle_switched && !scheduler_switched;

    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "rust_run_cycle_orchestrator_handoff_side_effect_detected",
            Some("rust_run_cycle_orchestrator_handoff_contract".to_string()),
            "Run_cycle orchestrator handoff detected cleanup/apply/write/Python-removal/run_cycle-switch side effects, which are forbidden in this release.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && handoff_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "rust_run_cycle_orchestrator_handoff_gates_not_enabled",
            Some("rust_core".to_string()),
            "Rust run_cycle orchestrator handoff gates are not fully enabled; report remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_scheduler_handoff || scheduler_ready)
        && shadow_age <= max_shadow_age
        && require_python_fallback
        && run_cycle_ready
        && config_state_ready
        && side_effect_free;

    let review = errors.is_empty() && scheduler_ready && run_cycle_ready && config_state_ready && side_effect_free;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "rust_run_cycle_orchestrator_handoff_contract_ready"
    } else if review {
        "rust_run_cycle_orchestrator_handoff_contract_review"
    } else {
        "rust_run_cycle_orchestrator_handoff_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("scheduler_status".to_string(), json!(scheduler_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("run_cycle_shadow_count".to_string(), json!(run_cycle_shadow_count));

    let mut contract_steps = Vec::new();
    for (idx, name) in [
        "mirror_python_run_cycle_inputs",
        "shadow_execute_run_cycle_graph",
        "compare_generated_manifests",
        "keep_python_run_cycle_authoritative",
        "defer_run_cycle_switch_to_future_release",
    ].iter().enumerate() {
        let mut step = Map::new();
        step.insert("step".to_string(), json!(idx + 1));
        step.insert("name".to_string(), json!(name));
        step.insert("mutating".to_string(), json!(false));
        contract_steps.push(Value::Object(step));
    }

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("rust_run_cycle_orchestrator_handoff_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("run_cycle_orchestrator_handoff_contract_id".to_string(), json!(handoff_id(&Value::Object(seed))));
    map.insert("rust_run_cycle_orchestrator_handoff_ready".to_string(), json!(ready));
    map.insert("scheduler_handoff_status".to_string(), json!(scheduler_status));
    map.insert("scheduler_handoff_ready".to_string(), json!(scheduler_ready));
    map.insert("run_cycle_orchestrator_manifest_ready".to_string(), json!(run_cycle_manifest_ready));
    map.insert("run_cycle_shadow_ready".to_string(), json!(run_cycle_ready));
    map.insert("run_cycle_shadow_count".to_string(), json!(run_cycle_shadow_count));
    map.insert("config_state_shadow_ready".to_string(), json!(config_state_ready));
    map.insert("config_state_shadow_count".to_string(), json!(config_state_shadow_count));
    map.insert("run_cycle_orchestrator_handoff_steps".to_string(), Value::Array(contract_steps));
    map.insert("webui_ux_unchanged".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("python_run_cycle_authoritative".to_string(), json!(true));
    map.insert("rust_run_cycle_authoritative".to_string(), json!(false));
    map.insert("rust_scheduler_authoritative".to_string(), json!(false));
    map.insert("rust_api_service_authoritative".to_string(), json!(false));
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
    map.insert("next_stage".to_string(), json!("rust_config_state_authority_handoff_contract"));
    map.insert("note".to_string(), json!("v5.3 builds the Rust run_cycle orchestrator handoff contract while keeping Python run_cycle authoritative and preserving the existing WebUI/UX."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_RUN_CYCLE_ORCHESTRATOR_HANDOFF));
        root.insert("shadow_age_seconds".to_string(), json!(10));
        root.insert("run_cycle_orchestrator_manifest_ready".to_string(), json!(true));
        root.insert("run_cycle_shadow_ready".to_string(), json!(true));
        root.insert("run_cycle_shadow_count".to_string(), json!(3));
        root.insert("config_state_shadow_ready".to_string(), json!(true));
        root.insert("config_state_shadow_count".to_string(), json!(3));

        let mut rust_core = Map::new();
        rust_core.insert("allow_rust_run_cycle_orchestrator_handoff_contract".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_contract_pilot".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_mode".to_string(), json!("contract_only"));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_scheduler_handoff".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_python_fallback".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_manual_confirmation".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_config_state_shadow".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_require_no_side_effects".to_string(), json!(true));
        rust_core.insert("rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rust_core));

        let mut scheduler_handoff = Map::new();
        scheduler_handoff.insert("status".to_string(), json!("rust_backend_scheduler_handoff_plan_ready"));
        scheduler_handoff.insert("rust_backend_scheduler_handoff_ready".to_string(), json!(true));
        scheduler_handoff.insert("rust_scheduler_authoritative".to_string(), json!(false));
        scheduler_handoff.insert("rust_run_cycle_authoritative".to_string(), json!(false));
        scheduler_handoff.insert("python_backend_required".to_string(), json!(true));
        root.insert("rust_backend_scheduler_handoff_plan".to_string(), Value::Object(scheduler_handoff));

        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_run_cycle_orchestrator_handoff_contract() {
        let (result, errors, _warnings) = build_rust_run_cycle_orchestrator_handoff_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_run_cycle_orchestrator_handoff_contract_shadow_only"));
        assert_eq!(result.get("rust_run_cycle_authoritative").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_and_run_cycle_switch_attempts() {
        let (result, errors, _warnings) = build_rust_run_cycle_orchestrator_handoff_contract_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_run_cycle_orchestrator_handoff_contract_without_switching_python_authority() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_rust_run_cycle_orchestrator_handoff_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_run_cycle_orchestrator_handoff_contract_ready"));
        assert_eq!(result.get("rust_run_cycle_orchestrator_handoff_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_run_cycle_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_run_cycle_authoritative").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("python_backend_required").and_then(Value::as_bool), Some(true));
    }
}
