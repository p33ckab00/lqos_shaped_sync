use crate::collector_authority_selection::build_collector_authority_selection_payload;
use crate::collector_bundle::build_collector_circuit_bundle_payload;
use crate::collector_parity::compare_collector_bundle_parity_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn config_value<'a>(payload: &'a Value, key: &str) -> Option<&'a Value> {
    payload
        .get("rust_core")
        .and_then(|v| v.get(key))
        .or_else(|| payload.get("config").and_then(|c| c.get("rust_core")).and_then(|v| v.get(key)))
}

fn rows_from_value(value: &Value) -> Vec<Value> {
    if let Some(items) = value.as_array() {
        return items.iter().filter(|v| v.is_object()).cloned().collect();
    }
    if let Some(obj) = value.as_object() {
        return obj.values().filter(|v| v.is_object()).cloned().collect();
    }
    Vec::new()
}

fn bundle_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("cad-{}", &digest[..16])
}

/// Build a non-mutating dry-run execution bundle for future Rust collector authority.
///
/// v3.8 still keeps Python collectors production-authoritative. This operation
/// combines the source selection from v3.7 with a Rust-shadow collector bundle
/// and a parity check so the WebUI/run_cycle can show what Rust would have
/// produced without allowing Rust output to drive cleanup, writes, or apply.
pub fn build_collector_authority_dry_run_bundle_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "dry_run"), "execute" | "promote" | "switch" | "authority" | "apply");
    if requested_execute {
        errors.push(Diagnostic::error(
            "collector_authority_dry_run_execute_not_implemented",
            Some("collector_authority_dry_run".to_string()),
            "This release only builds a dry-run Rust collector authority bundle. It does not execute live collection or switch authority away from Python.",
        ));
    }

    let allow_bundle = bool_value(config_value(payload, "allow_collector_authority_dry_run_bundle"), false);
    let bundle_pilot = bool_value(config_value(payload, "collector_authority_dry_run_bundle_pilot"), false);
    let allow_selection = bool_value(config_value(payload, "allow_collector_authority_dry_run_selection"), false);
    let selection_pilot = bool_value(config_value(payload, "collector_authority_dry_run_selection_pilot"), false);

    let selection_value = payload
        .get("collector_authority_selection")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_authority_selection"))
        .cloned();
    let (selection, selection_errors, mut selection_warnings) = match selection_value {
        Some(v) if v.is_object() => (v, Vec::new(), Vec::new()),
        _ => build_collector_authority_selection_payload(payload),
    };
    warnings.append(&mut selection_warnings);
    if !selection_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_selection_not_clean",
            Some("collector_authority_selection".to_string()),
            "Collector authority selection returned errors; dry-run bundle remains Python-only.",
        ));
    }

    let selection_ready = selection_errors.is_empty()
        && selection.get("status").and_then(Value::as_str) == Some("collector_authority_dry_run_selection_ready")
        && selection.get("rust_shadow_count").and_then(Value::as_u64).unwrap_or(0) > 0;

    let mut rust_bundle_result = json!({
        "mode": "collector_bundle_shadow",
        "normalized_count": 0,
        "normalized_rows": []
    });
    let mut rust_bundle_errors: Vec<Diagnostic> = Vec::new();
    let rust_shadow_requested = selection_ready && allow_bundle && bundle_pilot && allow_selection && selection_pilot;
    if rust_shadow_requested {
        let (bundle, bundle_errors, mut bundle_warnings) = build_collector_circuit_bundle_payload(payload);
        rust_bundle_result = bundle;
        rust_bundle_errors = bundle_errors;
        warnings.append(&mut bundle_warnings);
    } else {
        warnings.push(Diagnostic::warning(
            "collector_authority_dry_run_bundle_not_enabled",
            Some("collector_authority_dry_run".to_string()),
            "Rust-shadow collector dry-run bundle gates are not fully enabled; Python collectors remain selected.",
        ));
    }

    let rust_rows = rust_bundle_result
        .get("normalized_rows")
        .map(rows_from_value)
        .unwrap_or_default();
    let python_rows = payload
        .get("python_rows")
        .or_else(|| payload.get("python_authoritative_rows"))
        .map(rows_from_value)
        .unwrap_or_default();

    let mut parity_result = json!({
        "verdict": "not_available",
        "parity_score": 0.0,
        "exact_match": false,
        "python_count": python_rows.len(),
        "rust_count": rust_rows.len()
    });
    let mut parity_errors: Vec<Diagnostic> = Vec::new();
    if !python_rows.is_empty() || !rust_rows.is_empty() {
        let (parity, p_errors, mut p_warnings) = compare_collector_bundle_parity_payload(&json!({
            "python_rows": python_rows,
            "rust_rows": rust_rows,
            "strict": false
        }));
        parity_result = parity;
        parity_errors = p_errors;
        warnings.append(&mut p_warnings);
    }

    let parity_pass = parity_errors.is_empty()
        && parity_result.get("verdict").and_then(Value::as_str) == Some("parity_pass");
    let rust_count = rust_bundle_result.get("normalized_count").and_then(Value::as_u64).unwrap_or(0);

    let status = if !errors.is_empty() {
        "blocked"
    } else if rust_shadow_requested && rust_bundle_errors.is_empty() && parity_pass {
        "collector_authority_dry_run_bundle_ready"
    } else if rust_shadow_requested && rust_bundle_errors.is_empty() && rust_count > 0 {
        "collector_authority_dry_run_bundle_review"
    } else if rust_shadow_requested {
        "collector_authority_dry_run_bundle_partial"
    } else {
        "collector_authority_dry_run_bundle_python_only"
    };

    let seed = json!({
        "status": status,
        "selection_id": selection.get("selection_id"),
        "rust_count": rust_count,
        "parity": parity_result.get("verdict"),
    });

    let result = json!({
        "mode": "collector_authority_dry_run_bundle",
        "status": status,
        "dry_run_bundle_id": bundle_id(&seed),
        "collector_authority": "python_authoritative",
        "production_authority": "python_collector",
        "dry_run_authority": if rust_shadow_requested { "rust_shadow_candidate" } else { "python_collector" },
        "selection": selection,
        "rust_shadow_requested": rust_shadow_requested,
        "allow_dry_run_bundle": allow_bundle,
        "dry_run_bundle_pilot": bundle_pilot,
        "rust_bundle": rust_bundle_result,
        "rust_bundle_error_count": rust_bundle_errors.len(),
        "parity": parity_result,
        "parity_error_count": parity_errors.len(),
        "normalized_count": rust_count,
        "full_rust_backend": false,
        "collector_authority_switch_supported": false,
        "collector_output_can_drive_cleanup": false,
        "collector_output_can_drive_apply": false,
        "python_collector_fallback_required": true,
        "safe_for_cleanup": false,
        "write_allowed": false,
        "apply_allowed": false,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "next_stage": "rust_collector_authority_shadow_run_cycle_integration",
        "note": "v3.8 builds an auditable Rust-shadow collector dry-run bundle only. It does not switch production collector authority or allow cleanup/apply from Rust output."
    });

    for err in rust_bundle_errors.into_iter().chain(parity_errors.into_iter()) {
        warnings.push(Diagnostic::warning(
            err.code,
            err.path,
            err.message,
        ));
    }

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn pppoe_payload() -> Value {
        let rows = json!([
            {"Circuit ID":"selftest", "Circuit Name":"selftest", "Device ID":"selftest", "Device Name":"selftest", "Parent Node":"15M-RB5009", "MAC":"AA:BB:CC:DD:EE:FF", "IPv4":"10.0.0.2", "IPv6":"", "Download Min Mbps":"7.5", "Upload Min Mbps":"7.5", "Download Max Mbps":"15", "Upload Max Mbps":"15", "Comment":"PPP"}
        ]);
        json!({
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"dry-run-bundle-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
            "sources": ["pppoe"],
            "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
            "python_rows": rows,
            "pppoe": {
                "active": [{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
                "secrets": [{"name":"selftest", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
                "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
            }
        })
    }

    #[test]
    fn defaults_to_python_only_bundle() {
        let payload = pppoe_payload();
        let (result, errors, _warnings) = build_collector_authority_dry_run_bundle_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_dry_run_bundle_python_only"));
        assert_eq!(result.get("collector_authority").and_then(Value::as_str), Some("python_authoritative"));
        assert_eq!(result.get("safe_for_cleanup").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn builds_ready_dry_run_bundle_when_gates_are_enabled() {
        let mut payload = pppoe_payload();
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("rust_core".to_string(), json!({
                "allow_rust_collector_authority": true,
                "rust_collector_authority_pilot": true,
                "allow_rust_routeros_live_read_adapter": true,
                "routeros_live_read_adapter_pilot": true,
                "rust_collector_authority_sources": ["pppoe"],
                "collector_authority_mode": "rust_collector_authority_pilot",
                "collector_authority_manifest_pilot": true,
                "allow_collector_authority_manifest": true,
                "collector_authority_dry_run_selection_pilot": true,
                "allow_collector_authority_dry_run_selection": true,
                "collector_authority_dry_run_bundle_pilot": true,
                "allow_collector_authority_dry_run_bundle": true
            }));
        }
        let (result, errors, _warnings) = build_collector_authority_dry_run_bundle_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_dry_run_bundle_ready"));
        assert_eq!(result.get("normalized_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("collector_output_can_drive_cleanup").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = pppoe_payload();
        if let Some(obj) = payload.as_object_mut() { obj.insert("execute".to_string(), json!(true)); }
        let (_result, errors, _warnings) = build_collector_authority_dry_run_bundle_payload(&payload);
        assert!(!errors.is_empty());
    }
}
