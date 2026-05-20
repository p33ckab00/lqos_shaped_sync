use crate::protocol::Diagnostic;
use crate::rust_circuit_builder_authority_handoff::build_rust_circuit_builder_authority_handoff_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_SYNC_ENGINE_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT";
const CONFIRM_CIRCUIT_BUILDER_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT";

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
    format!("synchandoff-{}", &digest[..16])
}

/// Build a Rust sync engine authority handoff contract while Python remains fallback.
///
/// v5.7 moves the full-Rust-backend track from circuit builder authority toward
/// sync engine authority. It validates the circuit builder handoff, sync-plan
/// shadow output, diff/apply-manifest preview parity, cleanup safety, and Python
/// fallback. It does not switch production sync engine authority to Rust and
/// does not remove Python.
pub fn build_rust_sync_engine_authority_handoff_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "commit" | "switch" | "remove-python" | "replace-sync-engine" | "production" | "authoritative" | "sync-live" | "apply"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_sync_engine_authority_handoff_execute_not_implemented",
            Some("rust_sync_engine_authority_handoff_contract".to_string()),
            "This release only builds a Rust sync engine authority handoff contract. It does not switch sync authority, run live apply, or remove Python.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_rust_sync_engine_authority_handoff_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_contract_pilot"), false);
    let handoff_mode = str_value(config_value(payload, "rust_sync_engine_authority_handoff_mode"), "contract_only");
    let require_circuit_builder = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_circuit_builder_authority"), true);
    let require_python_fallback = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_manual_confirmation"), true);
    let require_sync_plan_shadow = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_sync_plan_shadow"), true);
    let require_diff_parity = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_diff_parity"), true);
    let require_apply_manifest_preview = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_apply_manifest_preview"), true);
    let require_cleanup_safety = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_cleanup_safety"), true);
    let require_no_side_effects = bool_value(config_value(payload, "rust_sync_engine_authority_handoff_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "rust_sync_engine_authority_handoff_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_SYNC_ENGINE_AUTHORITY_HANDOFF;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_confirmation_required",
            Some("confirmation".to_string()),
            "Rust sync engine authority handoff requires CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "rust_sync_engine_authority_handoff_requires_python_fallback",
            Some("rust_core.rust_sync_engine_authority_handoff_require_python_fallback".to_string()),
            "v5.7 still requires Python sync engine backend as fallback. Python removal belongs to a later full-backend execution phase.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; sync engine authority handoff remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let circuit_value = first_object(payload, &[
        "rust_circuit_builder_authority_handoff_contract",
        "circuit_builder_authority_handoff_contract",
        "rust_circuit_builder_authority_handoff",
    ]).cloned();

    let (circuit_handoff, circuit_errors, mut circuit_warnings) = match circuit_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("rust_circuit_builder_authority_handoff_confirmation"),
                    CONFIRM_CIRCUIT_BUILDER_AUTHORITY_HANDOFF,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_rust_circuit_builder_authority_handoff_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut circuit_warnings);

    if !circuit_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_circuit_builder_not_clean",
            Some("rust_circuit_builder_authority_handoff_contract".to_string()),
            "Rust circuit builder authority handoff returned errors; sync engine authority handoff remains shadow-only.",
        ));
    }

    let circuit_status = circuit_handoff.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let circuit_ready = circuit_errors.is_empty()
        && circuit_status == "rust_circuit_builder_authority_handoff_contract_ready"
        && circuit_handoff.get("rust_circuit_builder_authority_handoff_ready").and_then(Value::as_bool).unwrap_or(false)
        && circuit_handoff.get("rust_circuit_builder_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && circuit_handoff.get("python_circuit_builder_authoritative").and_then(Value::as_bool).unwrap_or(true);

    if require_circuit_builder && !circuit_ready {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_circuit_builder_not_ready",
            Some("rust_circuit_builder_authority_handoff_contract".to_string()),
            "Rust circuit builder authority handoff contract has not passed; sync engine authority handoff remains shadow-only or under review.",
        ));
    }

    let sync_plan_shadow_ready = bool_value(payload.get("sync_plan_shadow_ready"), false);
    let sync_plan_shadow_count = number_value(payload.get("sync_plan_shadow_count"), 0);
    let sync_plan_ready = !require_sync_plan_shadow || (sync_plan_shadow_ready && sync_plan_shadow_count > 0);
    if require_sync_plan_shadow && !sync_plan_ready {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_sync_plan_shadow_required",
            Some("sync_plan_shadow_ready".to_string()),
            "Rust sync engine authority handoff requires sync-plan shadow verification before it can report ready.",
        ));
    }

    let diff_parity_ready = bool_value(payload.get("sync_diff_parity_ready"), false);
    let diff_parity_score = payload.get("sync_diff_parity_score").and_then(Value::as_f64).unwrap_or(0.0);
    let diff_ready = !require_diff_parity || (diff_parity_ready && diff_parity_score >= 99.0);
    if require_diff_parity && !diff_ready {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_diff_parity_required",
            Some("sync_diff_parity_ready".to_string()),
            "Rust sync engine authority handoff requires diff parity before it can report ready.",
        ));
    }

    let apply_preview_ready = bool_value(payload.get("apply_manifest_preview_ready"), false);
    let apply_preview_blockers = number_value(payload.get("apply_manifest_preview_blocker_count"), 0);
    let apply_preview_ok = !require_apply_manifest_preview || (apply_preview_ready && apply_preview_blockers == 0);
    if require_apply_manifest_preview && !apply_preview_ok {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_apply_preview_required",
            Some("apply_manifest_preview_ready".to_string()),
            "Rust sync engine authority handoff requires non-mutating apply-manifest preview verification before it can report ready.",
        ));
    }

    let cleanup_safety_ready = bool_value(payload.get("cleanup_safety_ready"), false);
    let cleanup_candidate_count = number_value(payload.get("cleanup_candidate_count"), 0);
    let cleanup_ready = !require_cleanup_safety || (cleanup_safety_ready && cleanup_candidate_count == 0);
    if require_cleanup_safety && !cleanup_ready {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_cleanup_safety_required",
            Some("cleanup_safety_ready".to_string()),
            "Rust sync engine authority handoff requires cleanup safety verification before it can report ready.",
        ));
    }

    let side_effect_free = !bool_value(payload.get("sync_engine_authority_switched_to_rust"), false)
        && !bool_value(payload.get("python_backend_removed"), false)
        && !bool_value(payload.get("shaped_devices_write_attempted"), false)
        && !bool_value(payload.get("config_write_attempted"), false)
        && !bool_value(payload.get("state_write_attempted"), false)
        && !bool_value(payload.get("apply_attempted"), false)
        && !bool_value(payload.get("cleanup_attempted"), false);
    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "rust_sync_engine_authority_handoff_side_effect_detected",
            Some("rust_sync_engine_authority_handoff_contract".to_string()),
            "Rust sync engine authority handoff detected forbidden side effects. This phase is contract-only and non-mutating.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && handoff_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "rust_sync_engine_authority_handoff_gates_not_enabled",
            Some("rust_core".to_string()),
            "Rust sync engine authority handoff gates are not fully enabled; contract remains shadow-only.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_circuit_builder || circuit_ready)
        && require_python_fallback
        && sync_plan_ready
        && diff_ready
        && apply_preview_ok
        && cleanup_ready
        && side_effect_free
        && shadow_age <= max_shadow_age;

    let review = errors.is_empty()
        && circuit_ready
        && sync_plan_ready
        && diff_ready
        && apply_preview_ok
        && cleanup_ready
        && side_effect_free;

    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "rust_sync_engine_authority_handoff_contract_ready"
    } else if review {
        "rust_sync_engine_authority_handoff_contract_review"
    } else {
        "rust_sync_engine_authority_handoff_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("circuit_status".to_string(), json!(circuit_status));
    seed.insert("sync_plan_shadow_count".to_string(), json!(sync_plan_shadow_count));
    seed.insert("diff_parity_score".to_string(), json!(diff_parity_score));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("rust_sync_engine_authority_handoff_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("sync_engine_handoff_id".to_string(), json!(handoff_id(&Value::Object(seed))));
    map.insert("rust_sync_engine_authority_handoff_ready".to_string(), json!(ready));
    map.insert("circuit_builder_authority_handoff_ready".to_string(), json!(circuit_ready));
    map.insert("sync_plan_shadow_ready".to_string(), json!(sync_plan_ready));
    map.insert("sync_diff_parity_ready".to_string(), json!(diff_ready));
    map.insert("apply_manifest_preview_ready".to_string(), json!(apply_preview_ok));
    map.insert("cleanup_safety_ready".to_string(), json!(cleanup_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("python_sync_engine_authoritative".to_string(), json!(true));
    map.insert("rust_sync_engine_authoritative".to_string(), json!(false));
    map.insert("python_circuit_builder_authoritative".to_string(), json!(true));
    map.insert("rust_circuit_builder_authoritative".to_string(), json!(false));
    map.insert("rust_live_collector_authoritative".to_string(), json!(false));
    map.insert("rust_config_state_authoritative".to_string(), json!(false));
    map.insert("rust_run_cycle_authoritative".to_string(), json!(false));
    map.insert("rust_api_service_authoritative".to_string(), json!(false));
    map.insert("rust_apply_authoritative".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("side_effect_free".to_string(), json!(side_effect_free));
    map.insert("manual_confirmation_accepted".to_string(), json!(confirmation_ok));
    map.insert("gates_ready".to_string(), json!(gates_ready));
    map.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    map.insert("max_shadow_age_seconds".to_string(), json!(max_shadow_age));
    map.insert("next_stage".to_string(), json!("rust_apply_journal_authority_handoff_contract"));
    map.insert("note".to_string(), json!("v5.7 prepares Rust sync engine authority while keeping Python authoritative and WebUI/UX unchanged."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_SYNC_ENGINE_AUTHORITY_HANDOFF));
        root.insert("shadow_age_seconds".to_string(), json!(30));
        root.insert("sync_plan_shadow_ready".to_string(), json!(true));
        root.insert("sync_plan_shadow_count".to_string(), json!(3));
        root.insert("sync_diff_parity_ready".to_string(), json!(true));
        root.insert("sync_diff_parity_score".to_string(), json!(100.0));
        root.insert("apply_manifest_preview_ready".to_string(), json!(true));
        root.insert("apply_manifest_preview_blocker_count".to_string(), json!(0));
        root.insert("cleanup_safety_ready".to_string(), json!(true));
        root.insert("cleanup_candidate_count".to_string(), json!(0));

        let mut rc = Map::new();
        rc.insert("allow_rust_sync_engine_authority_handoff_contract".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_contract_pilot".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_mode".to_string(), json!("contract_only"));
        rc.insert("rust_sync_engine_authority_handoff_require_circuit_builder_authority".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_python_fallback".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_manual_confirmation".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_sync_plan_shadow".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_diff_parity".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_apply_manifest_preview".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_cleanup_safety".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_require_no_side_effects".to_string(), json!(true));
        rc.insert("rust_sync_engine_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut circuit = Map::new();
        circuit.insert("status".to_string(), json!("rust_circuit_builder_authority_handoff_contract_ready"));
        circuit.insert("rust_circuit_builder_authority_handoff_ready".to_string(), json!(true));
        circuit.insert("rust_circuit_builder_authoritative".to_string(), json!(false));
        circuit.insert("python_circuit_builder_authoritative".to_string(), json!(true));
        circuit.insert("python_backend_fallback_required".to_string(), json!(true));
        root.insert("rust_circuit_builder_authority_handoff_contract".to_string(), Value::Object(circuit));
        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_sync_engine_handoff() {
        let (result, errors, _warnings) = build_rust_sync_engine_authority_handoff_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_sync_engine_authority_handoff_contract_shadow_only"));
        assert_eq!(result.get("rust_sync_engine_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_sync_engine_authoritative").and_then(Value::as_bool), Some(true));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_rust_sync_engine_authority_handoff_contract_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_contract_without_switching_authority() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_rust_sync_engine_authority_handoff_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_sync_engine_authority_handoff_contract_ready"));
        assert_eq!(result.get("rust_sync_engine_authority_handoff_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_sync_engine_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_sync_engine_authoritative").and_then(Value::as_bool), Some(true));
    }
}
