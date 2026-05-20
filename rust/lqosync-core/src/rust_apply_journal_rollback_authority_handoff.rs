use crate::protocol::Diagnostic;
use crate::rust_sync_engine_authority_handoff::build_rust_sync_engine_authority_handoff_contract_payload;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

const CONFIRM_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF_CONTRACT";
const CONFIRM_SYNC_ENGINE_AUTHORITY_HANDOFF: &str = "CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT";

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
    format!("applyjournalhandoff-{}", &digest[..16])
}

/// Build a Rust apply/journal/rollback authority handoff contract while Python remains fallback.
///
/// v5.8 moves the full-Rust-backend track from sync engine authority toward the
/// final apply, transaction journal, audit, and rollback authority layer. It remains
/// non-mutating: Rust does not write ShapedDevices live, does not apply LibreQoS,
/// does not append production journals, and does not remove Python.
pub fn build_rust_apply_journal_rollback_authority_handoff_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(
            str_value(payload.get("mode"), "contract"),
            "execute" | "commit" | "switch" | "remove-python" | "replace-apply" | "production" | "authoritative" | "apply-live" | "journal-live" | "rollback-live"
        );
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_apply_journal_rollback_authority_handoff_execute_not_implemented",
            Some("rust_apply_journal_rollback_authority_handoff_contract".to_string()),
            "This release only builds a Rust apply/journal/rollback authority handoff contract. It does not switch apply authority, write production journals, execute rollback, or remove Python.",
        ));
    }

    let allow_contract = bool_value(config_value(payload, "allow_rust_apply_journal_rollback_authority_handoff_contract"), false);
    let contract_pilot = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_contract_pilot"), false);
    let handoff_mode = str_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_mode"), "contract_only");
    let require_sync_engine = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority"), true);
    let require_python_fallback = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_python_fallback"), true);
    let require_manual_confirmation = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_manual_confirmation"), true);
    let require_apply_shadow = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_apply_shadow"), true);
    let require_journal_shadow = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_journal_shadow"), true);
    let require_rollback_shadow = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_rollback_shadow"), true);
    let require_audit_shadow = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_audit_shadow"), true);
    let require_no_side_effects = bool_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_require_no_side_effects"), true);
    let max_shadow_age = number_value(config_value(payload, "rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds"), 900);
    let shadow_age = number_value(payload.get("shadow_age_seconds"), 0);

    let confirmation = str_value(payload.get("confirmation"), "");
    let confirmation_ok = !require_manual_confirmation || confirmation == CONFIRM_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF;
    if require_manual_confirmation && !confirmation_ok {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_confirmation_required",
            Some("confirmation".to_string()),
            "Rust apply/journal/rollback authority handoff requires CONFIRM_RUST_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF_CONTRACT before it can report ready.",
        ));
    }

    if !require_python_fallback {
        errors.push(Diagnostic::error(
            "rust_apply_journal_rollback_authority_handoff_requires_python_fallback",
            Some("rust_core.rust_apply_journal_rollback_authority_handoff_require_python_fallback".to_string()),
            "v5.8 still requires Python apply/journal/rollback backend as fallback. Python removal belongs to a later full-backend execution phase.",
        ));
    }

    if shadow_age > max_shadow_age {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_shadow_stale",
            Some("shadow_age_seconds".to_string()),
            "Rust-shadow data is older than the configured maximum age; apply/journal/rollback authority handoff remains under review.",
        ).with_value(json!({"shadow_age_seconds": shadow_age, "max_shadow_age_seconds": max_shadow_age})));
    }

    let sync_value = first_object(payload, &[
        "rust_sync_engine_authority_handoff_contract",
        "sync_engine_authority_handoff_contract",
        "rust_sync_engine_authority_handoff",
    ]).cloned();

    let (sync_handoff, sync_errors, mut sync_warnings) = match sync_value {
        Some(v) => (v, Vec::new(), Vec::new()),
        None => {
            let mut nested_payload = payload.clone();
            if let Some(obj) = nested_payload.as_object_mut() {
                let nested_confirmation = str_value(
                    payload.get("rust_sync_engine_authority_handoff_confirmation"),
                    CONFIRM_SYNC_ENGINE_AUTHORITY_HANDOFF,
                );
                obj.insert("confirmation".to_string(), json!(nested_confirmation));
            }
            build_rust_sync_engine_authority_handoff_contract_payload(&nested_payload)
        }
    };
    warnings.append(&mut sync_warnings);

    if !sync_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_sync_engine_not_clean",
            Some("rust_sync_engine_authority_handoff_contract".to_string()),
            "Rust sync engine authority handoff returned errors; apply/journal/rollback authority handoff remains shadow-only.",
        ));
    }

    let sync_status = sync_handoff.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let sync_ready = sync_errors.is_empty()
        && sync_status == "rust_sync_engine_authority_handoff_contract_ready"
        && sync_handoff.get("rust_sync_engine_authority_handoff_ready").and_then(Value::as_bool).unwrap_or(false)
        && sync_handoff.get("rust_sync_engine_authoritative").and_then(Value::as_bool).unwrap_or(false) == false
        && sync_handoff.get("python_sync_engine_authoritative").and_then(Value::as_bool).unwrap_or(true);

    if require_sync_engine && !sync_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_sync_engine_not_ready",
            Some("rust_sync_engine_authority_handoff_contract".to_string()),
            "Rust sync engine authority handoff contract has not passed; apply/journal/rollback authority handoff remains shadow-only or under review.",
        ));
    }

    let apply_shadow_ready = bool_value(payload.get("apply_transaction_shadow_ready"), false)
        && bool_value(payload.get("apply_manifest_replay_ready"), false)
        && number_value(payload.get("apply_transaction_shadow_blocker_count"), 0) == 0;
    if require_apply_shadow && !apply_shadow_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_apply_shadow_required",
            Some("apply_transaction_shadow_ready".to_string()),
            "Rust apply/journal/rollback authority handoff requires apply transaction shadow verification before it can report ready.",
        ));
    }

    let journal_shadow_ready = bool_value(payload.get("transaction_journal_shadow_ready"), false)
        && bool_value(payload.get("journal_replay_parity_ready"), false)
        && number_value(payload.get("transaction_journal_shadow_error_count"), 0) == 0;
    if require_journal_shadow && !journal_shadow_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_journal_shadow_required",
            Some("transaction_journal_shadow_ready".to_string()),
            "Rust apply/journal/rollback authority handoff requires transaction journal shadow verification before it can report ready.",
        ));
    }

    let rollback_shadow_ready = bool_value(payload.get("rollback_manifest_shadow_ready"), false)
        && bool_value(payload.get("rollback_dry_run_ready"), false)
        && number_value(payload.get("rollback_shadow_blocker_count"), 0) == 0;
    if require_rollback_shadow && !rollback_shadow_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_rollback_shadow_required",
            Some("rollback_manifest_shadow_ready".to_string()),
            "Rust apply/journal/rollback authority handoff requires rollback manifest shadow verification before it can report ready.",
        ));
    }

    let audit_shadow_ready = bool_value(payload.get("audit_shadow_ready"), false)
        && bool_value(payload.get("audit_redaction_ready"), false)
        && number_value(payload.get("audit_shadow_error_count"), 0) == 0;
    if require_audit_shadow && !audit_shadow_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_audit_shadow_required",
            Some("audit_shadow_ready".to_string()),
            "Rust apply/journal/rollback authority handoff requires audit shadow verification before it can report ready.",
        ));
    }

    let side_effect_free = !any_side_effect(payload);
    if require_no_side_effects && !side_effect_free {
        errors.push(Diagnostic::error(
            "rust_apply_journal_rollback_authority_handoff_side_effect_detected",
            Some("rust_apply_journal_rollback_authority_handoff_contract".to_string()),
            "Apply/journal/rollback handoff side effects are forbidden in this release.",
        ));
    }

    let gates_ready = allow_contract && contract_pilot && handoff_mode == "contract_only";
    if !gates_ready {
        warnings.push(Diagnostic::warning(
            "rust_apply_journal_rollback_authority_handoff_gates_not_enabled",
            Some("rust_core".to_string()),
            "Rust apply/journal/rollback authority handoff gates are not enabled.",
        ));
    }

    let ready = errors.is_empty()
        && gates_ready
        && confirmation_ok
        && (!require_sync_engine || sync_ready)
        && require_python_fallback
        && (!require_apply_shadow || apply_shadow_ready)
        && (!require_journal_shadow || journal_shadow_ready)
        && (!require_rollback_shadow || rollback_shadow_ready)
        && (!require_audit_shadow || audit_shadow_ready)
        && side_effect_free
        && shadow_age <= max_shadow_age;
    let review = errors.is_empty()
        && sync_ready
        && apply_shadow_ready
        && journal_shadow_ready
        && rollback_shadow_ready
        && audit_shadow_ready
        && side_effect_free;
    let status = if !errors.is_empty() {
        "blocked"
    } else if ready {
        "rust_apply_journal_rollback_authority_handoff_contract_ready"
    } else if review {
        "rust_apply_journal_rollback_authority_handoff_contract_review"
    } else {
        "rust_apply_journal_rollback_authority_handoff_contract_shadow_only"
    };

    let mut seed = Map::new();
    seed.insert("status".to_string(), json!(status));
    seed.insert("sync_status".to_string(), json!(sync_status));
    seed.insert("shadow_age_seconds".to_string(), json!(shadow_age));
    seed.insert("confirmation_ok".to_string(), json!(confirmation_ok));

    let mut map = Map::new();
    map.insert("mode".to_string(), json!("rust_apply_journal_rollback_authority_handoff_contract"));
    map.insert("status".to_string(), json!(status));
    map.insert("handoff_contract_id".to_string(), json!(handoff_id(&Value::Object(seed))));
    map.insert("rust_apply_journal_rollback_authority_handoff_ready".to_string(), json!(ready));
    map.insert("sync_engine_authority_handoff_ready".to_string(), json!(sync_ready));
    map.insert("apply_transaction_shadow_ready".to_string(), json!(apply_shadow_ready));
    map.insert("transaction_journal_shadow_ready".to_string(), json!(journal_shadow_ready));
    map.insert("rollback_manifest_shadow_ready".to_string(), json!(rollback_shadow_ready));
    map.insert("audit_shadow_ready".to_string(), json!(audit_shadow_ready));
    map.insert("webui_ux_unchanged".to_string(), json!(true));
    map.insert("full_rust_backend".to_string(), json!(false));
    map.insert("python_backend_removable".to_string(), json!(false));
    map.insert("python_backend_removed".to_string(), json!(false));
    map.insert("python_backend_required".to_string(), json!(true));
    map.insert("python_backend_fallback_required".to_string(), json!(true));
    map.insert("python_apply_journal_rollback_authoritative".to_string(), json!(true));
    map.insert("rust_apply_journal_rollback_authoritative".to_string(), json!(false));
    map.insert("python_sync_engine_authoritative".to_string(), json!(true));
    map.insert("rust_sync_engine_authoritative".to_string(), json!(false));
    map.insert("safe_for_cleanup".to_string(), json!(false));
    map.insert("write_allowed".to_string(), json!(false));
    map.insert("apply_allowed".to_string(), json!(false));
    map.insert("journal_append_allowed".to_string(), json!(false));
    map.insert("rollback_execute_allowed".to_string(), json!(false));
    map.insert("next_stage".to_string(), json!("rust_backend_service_runtime_handoff_contract"));
    map.insert("note".to_string(), json!("v5.8 builds a non-mutating Rust apply/journal/rollback authority handoff contract while keeping Python authoritative and WebUI/UX unchanged."));

    (Value::Object(map), errors, warnings)
}

fn any_side_effect(payload: &Value) -> bool {
    bool_value(payload.get("apply_authority_switched_to_rust"), false)
        || bool_value(payload.get("journal_authority_switched_to_rust"), false)
        || bool_value(payload.get("rollback_authority_switched_to_rust"), false)
        || bool_value(payload.get("python_backend_removed"), false)
        || bool_value(payload.get("shaped_devices_write_attempted"), false)
        || bool_value(payload.get("config_write_attempted"), false)
        || bool_value(payload.get("state_write_attempted"), false)
        || bool_value(payload.get("audit_write_attempted"), false)
        || bool_value(payload.get("journal_append_attempted"), false)
        || bool_value(payload.get("rollback_execute_attempted"), false)
        || bool_value(payload.get("apply_attempted"), false)
        || bool_value(payload.get("cleanup_attempted"), false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready_payload() -> Value {
        let mut payload = Map::new();
        payload.insert("confirmation".to_string(), json!(CONFIRM_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF));
        payload.insert("shadow_age_seconds".to_string(), json!(30));
        payload.insert("apply_transaction_shadow_ready".to_string(), json!(true));
        payload.insert("apply_manifest_replay_ready".to_string(), json!(true));
        payload.insert("apply_transaction_shadow_blocker_count".to_string(), json!(0));
        payload.insert("transaction_journal_shadow_ready".to_string(), json!(true));
        payload.insert("journal_replay_parity_ready".to_string(), json!(true));
        payload.insert("transaction_journal_shadow_error_count".to_string(), json!(0));
        payload.insert("rollback_manifest_shadow_ready".to_string(), json!(true));
        payload.insert("rollback_dry_run_ready".to_string(), json!(true));
        payload.insert("rollback_shadow_blocker_count".to_string(), json!(0));
        payload.insert("audit_shadow_ready".to_string(), json!(true));
        payload.insert("audit_redaction_ready".to_string(), json!(true));
        payload.insert("audit_shadow_error_count".to_string(), json!(0));

        let mut rc = Map::new();
        rc.insert("allow_rust_apply_journal_rollback_authority_handoff_contract".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_contract_pilot".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_mode".to_string(), json!("contract_only"));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_python_fallback".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_manual_confirmation".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_apply_shadow".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_journal_shadow".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_rollback_shadow".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_audit_shadow".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_require_no_side_effects".to_string(), json!(true));
        rc.insert("rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        payload.insert("rust_core".to_string(), Value::Object(rc));

        let mut sync = Map::new();
        sync.insert("status".to_string(), json!("rust_sync_engine_authority_handoff_contract_ready"));
        sync.insert("rust_sync_engine_authority_handoff_ready".to_string(), json!(true));
        sync.insert("rust_sync_engine_authoritative".to_string(), json!(false));
        sync.insert("python_sync_engine_authoritative".to_string(), json!(true));
        payload.insert("rust_sync_engine_authority_handoff_contract".to_string(), Value::Object(sync));

        Value::Object(payload)
    }

    #[test]
    fn defaults_to_shadow_only_apply_journal_rollback_handoff() {
        let (result, errors, _warnings) = build_rust_apply_journal_rollback_authority_handoff_contract_payload(&json!({}));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_apply_journal_rollback_authority_handoff_contract_shadow_only"));
        assert_eq!(result.get("rust_apply_journal_rollback_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_apply_journal_rollback_authoritative").and_then(Value::as_bool), Some(true));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = ready_payload();
        payload.as_object_mut().unwrap().insert("execute".to_string(), json!(true));
        let (result, errors, _warnings) = build_rust_apply_journal_rollback_authority_handoff_contract_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }

    #[test]
    fn builds_ready_apply_journal_rollback_handoff_without_switching_authority() {
        let payload = ready_payload();
        let (result, errors, _warnings) = build_rust_apply_journal_rollback_authority_handoff_contract_payload(&payload);
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("rust_apply_journal_rollback_authority_handoff_contract_ready"));
        assert_eq!(result.get("rust_apply_journal_rollback_authority_handoff_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_apply_journal_rollback_authoritative").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("python_apply_journal_rollback_authoritative").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("apply_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("journal_append_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("rollback_execute_allowed").and_then(Value::as_bool), Some(false));
    }
}
