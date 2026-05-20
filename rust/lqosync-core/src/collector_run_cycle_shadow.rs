
use crate::collector_authority_dry_run::build_collector_authority_dry_run_bundle_payload;
use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn config_value<'a>(payload: &'a Value, key: &str) -> Option<&'a Value> {
    payload
        .get("rust_core")
        .and_then(|v| v.get(key))
        .or_else(|| payload.get("config").and_then(|c| c.get("rust_core")).and_then(|v| v.get(key)))
}

fn report_id(value: &Value) -> String {
    let text = serde_json::to_string(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    let digest = hex::encode(hasher.finalize());
    format!("rcrs-{}", &digest[..16])
}

fn array_len(value: Option<&Value>) -> usize {
    value.and_then(Value::as_array).map(|v| v.len()).unwrap_or(0)
}

/// Build a non-mutating run_cycle Rust-shadow integration report.
///
/// v3.9 is the first bridge for Python run_cycle to carry a Rust-shadow collector
/// dry-run bundle beside the authoritative Python collector output. Rust output is
/// diagnostic only: it cannot drive cleanup, generated files, LibreQoS apply, or
/// policy authority in this release.
pub fn build_run_cycle_rust_shadow_report_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(payload.get("mode").and_then(Value::as_str).unwrap_or("shadow"), "execute" | "apply" | "authority" | "promote" | "switch");
    if requested_execute {
        errors.push(Diagnostic::error(
            "run_cycle_rust_shadow_execute_not_implemented",
            Some("run_cycle_rust_shadow".to_string()),
            "This release only builds a run_cycle Rust-shadow report. It does not execute live collection, switch authority, or apply output.",
        ));
    }

    let allow = bool_value(config_value(payload, "run_cycle_rust_shadow_report_enabled"), false);
    let pilot = bool_value(config_value(payload, "run_cycle_rust_shadow_report_pilot"), false);
    let include_rows = bool_value(config_value(payload, "run_cycle_rust_shadow_include_rows"), false)
        || bool_value(payload.get("include_rows"), false);

    let dry_run_value = payload
        .get("collector_authority_dry_run_bundle")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_authority_dry_run_bundle"))
        .cloned();

    let (dry_run_bundle, dry_run_errors, mut dry_run_warnings) = match dry_run_value {
        Some(v) if v.is_object() => (v, Vec::new(), Vec::new()),
        _ => build_collector_authority_dry_run_bundle_payload(payload),
    };
    warnings.append(&mut dry_run_warnings);

    if !dry_run_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "collector_authority_dry_run_bundle_not_clean",
            Some("collector_authority_dry_run_bundle".to_string()),
            "Collector authority dry-run bundle returned errors; run_cycle Rust-shadow report remains Python-only.",
        ));
    }

    let dry_run_status = dry_run_bundle.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let rust_shadow_ready = dry_run_errors.is_empty()
        && dry_run_status == "collector_authority_dry_run_bundle_ready"
        && dry_run_bundle.get("normalized_count").and_then(Value::as_u64).unwrap_or(0) > 0;

    let python_row_count = array_len(payload.get("python_rows"))
        .max(array_len(payload.get("python_authoritative_rows")))
        .max(array_len(payload.get("existing_rows")));
    let rust_row_count = dry_run_bundle.get("normalized_count").and_then(Value::as_u64).unwrap_or(0);
    let parity_verdict = dry_run_bundle
        .get("parity")
        .and_then(|v| v.get("verdict"))
        .or_else(|| dry_run_bundle.get("parity"))
        .cloned()
        .unwrap_or_else(|| json!("not_available"));

    let report_active = allow && pilot && rust_shadow_ready;
    let status = if !errors.is_empty() {
        "blocked"
    } else if report_active {
        "run_cycle_rust_shadow_ready"
    } else if rust_shadow_ready {
        "run_cycle_rust_shadow_available_not_enabled"
    } else {
        "run_cycle_rust_shadow_python_only"
    };

    if !allow || !pilot {
        warnings.push(Diagnostic::warning(
            "run_cycle_rust_shadow_report_not_enabled",
            Some("run_cycle_rust_shadow".to_string()),
            "run_cycle Rust-shadow report gates are not fully enabled; Python run_cycle remains authoritative and no Rust-shadow bundle is selected for cycle comparison.",
        ));
    }

    let seed = json!({
        "status": status,
        "python_row_count": python_row_count,
        "rust_row_count": rust_row_count,
        "dry_run_status": dry_run_status,
        "parity_verdict": parity_verdict,
    });

    let mut shadow_bundle = dry_run_bundle.clone();
    if !include_rows {
        if let Some(obj) = shadow_bundle.as_object_mut() {
            if let Some(rust_bundle) = obj.get_mut("rust_bundle").and_then(Value::as_object_mut) {
                rust_bundle.remove("normalized_rows");
            }
        }
    }

    let result = json!({
        "mode": "run_cycle_rust_shadow_report",
        "status": status,
        "report_id": report_id(&seed),
        "collector_authority": "python_authoritative",
        "production_authority": "python_run_cycle",
        "shadow_authority": if report_active { "rust_shadow_diagnostic" } else { "disabled_or_python_only" },
        "report_enabled": allow,
        "report_pilot": pilot,
        "include_rows": include_rows,
        "rust_shadow_ready": rust_shadow_ready,
        "dry_run_status": dry_run_status,
        "python_row_count": python_row_count,
        "rust_row_count": rust_row_count,
        "parity_verdict": parity_verdict,
        "collector_authority_dry_run_bundle": shadow_bundle,
        "full_rust_backend": false,
        "python_run_cycle_authoritative": true,
        "rust_can_drive_cleanup": false,
        "rust_can_drive_apply": false,
        "rust_can_write_generated_files": false,
        "safe_for_cleanup": false,
        "write_allowed": false,
        "apply_allowed": false,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "next_stage": "rust_collector_authority_run_cycle_shadow_ui",
        "note": "v3.9 exposes a non-mutating run_cycle Rust-shadow report so Python can display Rust candidate collector output beside the authoritative Python cycle."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn pppoe_payload() -> Value {
        let row = json!({"Circuit ID":"selftest", "Circuit Name":"selftest", "Device ID":"selftest", "Device Name":"selftest", "Parent Node":"15M-RB5009", "MAC":"AA:BB:CC:DD:EE:FF", "IPv4":"10.0.0.2", "IPv6":"", "Download Min Mbps":"7.5", "Upload Min Mbps":"7.5", "Download Max Mbps":"15", "Upload Max Mbps":"15", "Comment":"PPP"});
        json!({
            "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"run-cycle-shadow-password", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
            "sources": ["pppoe"],
            "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
            "python_rows": [row],
            "pppoe": {
                "active": [{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
                "secrets": [{"name":"selftest", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
                "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
            }
        })
    }

    fn enable_gates(payload: &mut Value) {
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
                "allow_collector_authority_dry_run_bundle": true,
                "run_cycle_rust_shadow_report_enabled": true,
                "run_cycle_rust_shadow_report_pilot": true
            }));
        }
    }

    #[test]
    fn defaults_to_python_only_report() {
        let payload = pppoe_payload();
        let (result, errors, _warnings) = build_run_cycle_rust_shadow_report_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("run_cycle_rust_shadow_python_only"));
        assert_eq!(result.get("python_run_cycle_authoritative").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("rust_can_drive_cleanup").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn builds_ready_report_when_shadow_bundle_gates_are_enabled() {
        let mut payload = pppoe_payload();
        enable_gates(&mut payload);
        let (result, errors, _warnings) = build_run_cycle_rust_shadow_report_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("run_cycle_rust_shadow_ready"));
        assert_eq!(result.get("rust_row_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("safe_for_cleanup").and_then(Value::as_bool), Some(false));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("run-cycle-shadow-password"));
        assert!(!text.contains("\"password\":"));
    }

    #[test]
    fn blocks_execute_attempts() {
        let mut payload = pppoe_payload();
        enable_gates(&mut payload);
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("execute".to_string(), json!(true));
        }
        let (result, errors, _warnings) = build_run_cycle_rust_shadow_report_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
