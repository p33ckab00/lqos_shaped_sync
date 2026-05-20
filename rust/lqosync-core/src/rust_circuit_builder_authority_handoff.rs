use crate::protocol::Diagnostic;
use crate::rust_live_collector_authority_handoff::build_rust_live_collector_authority_handoff_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_CIRCUIT_BUILDER_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT";
const CONFIRM_LIVE_COLLECTOR_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_LIVE_COLLECTOR_AUTHORITY_HANDOFF_CONTRACT";

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
    format!("cbhandoff-{}", &digest[..16])
}

/// Build a Rust circuit builder authority handoff contract while Python remains fallback.
///
/// v5.6 moves the full-Rust-backend track from live collector authority toward
/// circuit row/build authority. It validates the live collector handoff,
/// circuit builder shadow output, ShapedDevices render parity, parent-node
/// integrity, and Python fallback. It does not switch production circuit builder
/// authority to Rust and does not remove Python.
pub fn build_rust_circuit_builder_authority_handoff_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "commit" | "switch" | "remove-python" | "replace-builder" | "production" | "authoritative" | "build-live"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_circuit_builder_authority_handoff_execute_not_implemented",
            Some("rust_circuit_builder_authority_handoff_contract".to_string()),
            "This release only builds a Rust circuit builder authority handoff contract. It does not switch circuit builder authority or remove Python.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_rust_circuit_builder_authority_handoff_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_contract_pilot"), false);
    let handoff_mode = str_value(config_value(payload, "rust_circuit_builder_authority_handoff_mode"), "contract_only");
    let require_live_collector = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_live_collector_authority"), true);
    let require_python_fallback = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_manual_confirmation"), true);
    let require_circuit_shadow = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_circuit_shadow"), true);
    let require_shaped_devices_parity = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_shaped_devices_parity"), true);
    let require_parent_integrity = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_parent_integrity"), true);
    let require_no_side_effects = bool_value(config_value(payload, "rust_circuit_builder_authority_handoff_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "rust_circuit_builder_authority_handoff_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_CIRCUIT_BUILDER_AUTHORITY_HANDOFF;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_confirmation_required",
            Some("confirmation".to_string()),
            "Rust circuit builder authority handoff requires CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "rust_circuit_builder_authority_handoff_requires_python_fallback",
            Some("rust_core.rust_circuit_builder_authority_handoff_require_python_fallback".to_string()),
            "v5.6 still requires Python circuit builder backend as fallback. Python removal belongs to a later full-backend execution phase.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; circuit builder authority handoff remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let live_collector_value = first_object(payload, &[
        "rust_live_collector_authority_handoff_contract",
        "live_collector_authority_handoff_contract",
        "rust_live_collector_authority_handoff",
    ]).cloned();

    let (live_collector_handoff, live_collector_errors, mut live_collector_warnings) = match live_collector_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("rust_live_collector_authority_handoff_confirmation"),
                    CONFIRM_LIVE_COLLECTOR_AUTHORITY_HANDOFF,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_rust_live_collector_authority_handoff_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut live_collector_warnings);

    if !live_collector_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_live_collector_not_clean",
            Some("rust_live_collector_authority_handoff_contract".to_string()),
            "Rust live collector authority handoff returned errors; circuit builder authority handoff remains shadow-only.",
        ));
    }

    let live_collector_status = live_collector_handoff.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let live_collector_ready = live_collector_errors.is_empty()
        && live_collector_status == "rust_live_collector_authority_handoff_contract_ready"
        && live_collector_handoff.get("rust_live_collector_authority_handoff_ready").and_then(Value::as_bool).unwrap_or(false)
        && live_collector_handoff.get("rust_live_collector_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && live_collector_handoff.get("python_live_collector_authoritative").and_then(Value::as_bool).unwrap_or(true);

    if require_live_collector && !live_collector_ready {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_live_collector_not_ready",
            Some("rust_live_collector_authority_handoff_contract".to_string()),
            "Rust live collector authority handoff contract has not passed; circuit builder authority handoff remains shadow-only or under review.",
        ));
    }

    let circuit_shadow_ready = bool_value(payload.get("circuit_builder_shadow_ready"), false);
    let circuit_shadow_count = number_value(payload.get("circuit_builder_shadow_count"), 0);
    let circuit_ready = !require_circuit_shadow || (circuit_shadow_ready && circuit_shadow_count > 0);
    if require_circuit_shadow && !circuit_ready {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_circuit_shadow_required",
            Some("circuit_builder_shadow_ready".to_string()),
            "Rust circuit builder authority handoff requires circuit builder shadow verification before it can report ready.",
        ));
    }

    let shaped_devices_parity_ready = bool_value(payload.get("shaped_devices_render_parity_ready"), false);
    let shaped_devices_parity_score = payload.get("shaped_devices_render_parity_score").and_then(Value::as_f64).unwrap_or(0.0);
    let shaped_ready = !require_shaped_devices_parity || (shaped_devices_parity_ready && shaped_devices_parity_score >= 99.0);
    if require_shaped_devices_parity && !shaped_ready {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_shaped_devices_parity_required",
            Some("shaped_devices_render_parity_ready".to_string()),
            "Rust circuit builder authority handoff requires ShapedDevices render parity before it can report ready.",
        ));
    }

    let parent_node_integrity_ready = bool_value(payload.get("parent_node_integrity_ready"), false);
    let parent_node_error_count = number_value(payload.get("parent_node_error_count"), 0);
    let parent_ready = !require_parent_integrity || (parent_node_integrity_ready && parent_node_error_count == 0);
    if require_parent_integrity && !parent_ready {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_parent_integrity_required",
            Some("parent_node_integrity_ready".to_string()),
            "Rust circuit builder authority handoff requires parent-node integrity before it can report ready.",
        ));
    }

    let side_effect_free = !bool_value(payload.get("circuit_builder_authority_switched_to_rust"), false)
        && !bool_value(payload.get("python_backend_removed"), false)
        && !bool_value(payload.get("shaped_devices_write_attempted"), false)
        && !bool_value(payload.get("config_write_attempted"), false)
        && !bool_value(payload.get("state_write_attempted"), false)
        && !bool_value(payload.get("apply_attempted"), false);
    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "rust_circuit_builder_authority_handoff_side_effect_detected",
            Some("rust_circuit_builder_authority_handoff_contract".to_string()),
            "Circuit builder authority handoff side effects are forbidden in this release.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && handoff_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "rust_circuit_builder_authority_handoff_gates_not_enabled",
            Some("rust_core".to_string()),
            "Rust circuit builder authority handoff gates are not enabled.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_live_collector || live_collector_ready)
        && require_python_fallback
        && circuit_ready
        && shaped_ready
        && parent_ready
        && side_effect_free
        && shadow_age <= max_shadow_age;
    let review = errors.is_empty() && live_collector_ready && circuit_ready && shaped_ready && parent_ready && side_effect_free;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "rust_circuit_builder_authority_handoff_contract_ready"
    } else if review {
        "rust_circuit_builder_authority_handoff_contract_review"
    } else {
        "rust_circuit_builder_authority_handoff_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("live_collector_status".to_string(), json!(live_collector_status));
    seed.insert("circuit_shadow_count".to_string(), json!(circuit_shadow_count));
    seed.insert("shaped_devices_render_parity_score".to_string(), json!(shaped_devices_parity_score));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("rust_circuit_builder_authority_handoff_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("circuit_builder_handoff_id".to_string(), json!(handoff_id(&Value::Object(seed))));
    map.insert("rust_circuit_builder_authority_handoff_ready".to_string(), json!(ready));
    map.insert("live_collector_authority_handoff_ready".to_string(), json!(live_collector_ready));
    map.insert("circuit_builder_shadow_ready".to_string(), json!(circuit_ready));
    map.insert("shaped_devices_render_parity_ready".to_string(), json!(shaped_ready));
    map.insert("parent_node_integrity_ready".to_string(), json!(parent_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("python_circuit_builder_authoritative".to_string(), json!(true));
    map.insert("rust_circuit_builder_authoritative".to_string(), json!(false));
    map.insert("python_live_collector_authoritative".to_string(), json!(true));
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
    map.insert("next_stage".to_string(), json!("rust_sync_engine_authority_handoff_contract"));
    map.insert("note".to_string(), json!("v5.6 prepares Rust circuit builder authority while keeping Python authoritative and WebUI/UX unchanged."));

    (Value::Object(map), errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut root = Map::new();
        root.insert("confirmation".to_string(), json!(CONFIRM_CIRCUIT_BUILDER_AUTHORITY_HANDOFF));
        root.insert("shadow_age_seconds".to_string(), json!(30));
        root.insert("circuit_builder_shadow_ready".to_string(), json!(true));
        root.insert("circuit_builder_shadow_count".to_string(), json!(3));
        root.insert("shaped_devices_render_parity_ready".to_string(), json!(true));
        root.insert("shaped_devices_render_parity_score".to_string(), json!(100.0));
        root.insert("parent_node_integrity_ready".to_string(), json!(true));
        root.insert("parent_node_error_count".to_string(), json!(0));

        let mut rc = Map::new();
        rc.insert("allow_rust_circuit_builder_authority_handoff_contract".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_contract_pilot".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_mode".to_string(), json!("contract_only"));
        rc.insert("rust_circuit_builder_authority_handoff_require_live_collector_authority".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_python_fallback".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_manual_confirmation".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_circuit_shadow".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_shaped_devices_parity".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_parent_integrity".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_require_no_side_effects".to_string(), json!(true));
        rc.insert("rust_circuit_builder_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        root.insert("rust_core".to_string(), Value::Object(rc));

        let mut live = Map::new();
        live.insert("status".to_string(), json!("rust_live_collector_authority_handoff_contract_ready"));
        live.insert("rust_live_collector_authority_handoff_ready".to_string(), json!(true));
        live.insert("rust_live_collector_authoritative".to_string(), json!(false));
        live.insert("python_live_collector_authoritative".to_string(), json!(true));
        live.insert("python_backend_fallback_required".to_string(), json!(true));
        root.insert("rust_live_collector_authority_handoff_contract".to_string(), Value::Object(live));
        Value::Object(root)
    }

    #[test]
    fn defaults_to_shadow_only_circuit_builder_handoff() {
        let (result, errors, _warnings) = build_rust_circuit_builder_authority_handoff_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_circuit_builder_authority_handoff_contract_shadow_only"));
        assert_eq!(result.get("rust_circuit_builder_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_circuit_builder_authoritative").and_then(Value::as_bool), Some(true));
    }

    #[test]
    fn blocks_execute_attempts() {
        let (result, errors, _warnings) = build_rust_circuit_builder_authority_handoff_contract_payload(&json!({"execute": true}));
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_contract_without_switching_authority() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_rust_circuit_builder_authority_handoff_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_circuit_builder_authority_handoff_contract_ready"));
        assert_eq!(result.get("rust_circuit_builder_authority_handoff_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_circuit_builder_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_circuit_builder_authoritative").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("write_allowed").and_then(Value::as_bool), Some(false));
    }
}
