use crate::protocol::Diagnostic;
use crate::routeros_live_read_adapter::run_routeros_live_read_adapter_pilot_payload;
use serde_json::{json, Value};

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

fn source_from_path(path: &str) -> &'static str {
    if path.starts_with("/ppp/") {
        "pppoe"
    } else if path.starts_with("/ip/dhcp-server") {
        "dhcp"
    } else if path.starts_with("/ip/hotspot") {
        "hotspot"
    } else {
        "unknown"
    }
}

fn source_allowed(payload: &Value, source: &str) -> bool {
    let maybe_list = config_value(payload, "rust_collector_authority_sources")
        .or_else(|| payload.get("rust_collector_authority_sources"));
    match maybe_list.and_then(Value::as_array) {
        Some(values) if !values.is_empty() => values.iter().any(|v| v.as_str() == Some(source) || v.as_str() == Some("all")),
        _ => false,
    }
}

fn parity_score(payload: &Value) -> f64 {
    payload
        .get("collector_parity")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_parity"))
        .and_then(|v| v.get("parity_score"))
        .and_then(Value::as_f64)
        .unwrap_or(0.0)
}

fn parity_verdict(payload: &Value) -> String {
    payload
        .get("collector_parity")
        .and_then(|v| v.get("result"))
        .or_else(|| payload.get("collector_parity"))
        .and_then(|v| v.get("verdict"))
        .and_then(Value::as_str)
        .unwrap_or("not_available")
        .to_string()
}

/// Evaluate whether a single collector source is eligible for a future Rust
/// collector authority pilot.
///
/// v3.5 is still a gate/contract only. It does not perform live RouterOS reads,
/// does not switch authority, and does not write files. Python collectors remain
/// authoritative unless a later release explicitly implements and enables the
/// live Rust collector adapter.
pub fn evaluate_rust_collector_authority_pilot_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let path = str_value(payload.get("path"), "/ppp/active");
    let source = str_value(payload.get("source"), source_from_path(path));
    let router = payload
        .get("router")
        .and_then(|v| v.get("name"))
        .and_then(Value::as_str)
        .or_else(|| payload.get("router").and_then(Value::as_str))
        .unwrap_or("unknown");

    let allow_collector_authority = bool_value(config_value(payload, "allow_rust_collector_authority"), false);
    let collector_authority_pilot = bool_value(config_value(payload, "rust_collector_authority_pilot"), false);
    let allow_live_adapter = bool_value(config_value(payload, "allow_rust_routeros_live_read_adapter"), false);
    let live_adapter_pilot = bool_value(config_value(payload, "routeros_live_read_adapter_pilot"), false);
    let authority_mode = config_value(payload, "collector_authority_mode")
        .and_then(Value::as_str)
        .unwrap_or("python_authoritative");
    let explicit_source_allowed = source_allowed(payload, source);
    let parity_score = parity_score(payload);
    let parity_verdict = parity_verdict(payload);
    let parity_ok = parity_score >= 99.99 || parity_verdict == "parity_pass";

    let mut adapter_payload = payload.clone();
    if let Value::Object(ref mut map) = adapter_payload {
        map.insert("adapter".to_string(), json!("contract"));
        map.insert("mode".to_string(), json!("contract"));
        map.insert("execute".to_string(), json!(false));
        map.entry("fixture_reply_words".to_string()).or_insert_with(|| json!(["!done"]));
    }
    let (live_adapter, adapter_errors, mut adapter_warnings) = run_routeros_live_read_adapter_pilot_payload(&adapter_payload);
    warnings.append(&mut adapter_warnings);
    if !adapter_errors.is_empty() {
        warnings.push(Diagnostic::warning(
            "live_read_adapter_contract_not_ready",
            Some("live_adapter".to_string()),
            "The live-read adapter contract returned errors; Rust collector authority cannot be piloted yet.",
        ));
    }

    let live_adapter_contract_ready = adapter_errors.is_empty()
        && live_adapter.get("status").and_then(Value::as_str) == Some("live_read_adapter_contract_ready");

    if !parity_ok {
        warnings.push(Diagnostic::warning(
            "collector_parity_not_proven",
            Some("collector_parity".to_string()),
            "Collector parity is not proven yet; Python collectors remain authoritative.",
        ).with_value(json!({"parity_score": parity_score, "verdict": parity_verdict})));
    }

    let gates_ready = allow_collector_authority
        && collector_authority_pilot
        && allow_live_adapter
        && live_adapter_pilot
        && explicit_source_allowed
        && parity_ok
        && live_adapter_contract_ready
        && authority_mode == "rust_collector_authority_pilot";

    let requested_execute = bool_value(payload.get("execute"), false)
        || matches!(str_value(payload.get("mode"), "contract"), "authority" | "promote" | "collector_authority");
    if requested_execute {
        errors.push(Diagnostic::error(
            "rust_collector_authority_switch_not_implemented",
            Some("collector_authority".to_string()),
            "This release only evaluates the Rust collector authority pilot gate. It does not switch collector authority away from Python.",
        ));
    }

    let status = if !errors.is_empty() {
        "blocked"
    } else if gates_ready {
        "collector_authority_pilot_gate_ready"
    } else {
        "collector_authority_shadow_only"
    };

    let missing_gates = json!({
        "allow_rust_collector_authority": !allow_collector_authority,
        "rust_collector_authority_pilot": !collector_authority_pilot,
        "allow_rust_routeros_live_read_adapter": !allow_live_adapter,
        "routeros_live_read_adapter_pilot": !live_adapter_pilot,
        "source_not_explicitly_allowed": !explicit_source_allowed,
        "collector_parity_not_proven": !parity_ok,
        "live_adapter_contract_not_ready": !live_adapter_contract_ready,
        "authority_mode_not_pilot": authority_mode != "rust_collector_authority_pilot"
    });

    let result = json!({
        "mode": "rust_collector_authority_pilot_gate",
        "status": status,
        "router": router,
        "source": source,
        "path": path,
        "authority_mode": authority_mode,
        "authority_required": "rust_collector_authority_pilot",
        "collector_authority": "python_authoritative",
        "future_collector_authority": if gates_ready { "rust_pilot_eligible" } else { "not_eligible" },
        "gates_ready": gates_ready,
        "missing_gates": missing_gates,
        "source_explicitly_allowed": explicit_source_allowed,
        "parity": {"score": parity_score, "verdict": parity_verdict, "ok": parity_ok},
        "live_adapter_contract_ready": live_adapter_contract_ready,
        "live_adapter": live_adapter,
        "full_rust_backend": false,
        "rust_collector_authority_switch_supported": false,
        "python_collector_fallback_required": true,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "safe_for_cleanup": false,
        "write_allowed": false,
        "apply_allowed": false,
        "next_stage": "rust_collector_live_read_pilot",
        "note": "v3.5 evaluates the Rust collector authority pilot gate only. It does not perform live reads, does not switch authority, and keeps Python collectors authoritative."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    #[test]
    fn defaults_to_shadow_only() {
        let leaked_password = "super-secret-password-value";
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password": leaked_password},
            "source": "pppoe",
            "path": "/ppp/active",
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"}
        });
        let (result, errors, _warnings) = evaluate_rust_collector_authority_pilot_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_shadow_only"));
        assert_eq!(result.get("collector_authority").and_then(Value::as_str), Some("python_authoritative"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains(leaked_password));
        assert!(!text.contains("\"password\":"));
    }

    #[test]
    fn reports_gate_ready_when_all_pilot_flags_and_parity_are_present() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"secret"},
            "source": "pppoe",
            "path": "/ppp/active",
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
            "rust_core": {
                "allow_rust_collector_authority": true,
                "rust_collector_authority_pilot": true,
                "allow_rust_routeros_live_read_adapter": true,
                "routeros_live_read_adapter_pilot": true,
                "rust_collector_authority_sources": ["pppoe"],
                "collector_authority_mode": "rust_collector_authority_pilot"
            }
        });
        let (result, errors, _warnings) = evaluate_rust_collector_authority_pilot_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("collector_authority_pilot_gate_ready"));
        assert_eq!(result.get("gates_ready").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("full_rust_backend").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_authority_switch_execution() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"secret"},
            "source": "pppoe",
            "execute": true,
            "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"}
        });
        let (result, errors, _warnings) = evaluate_rust_collector_authority_pilot_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert!(errors.iter().any(|e| e.code == "rust_collector_authority_switch_not_implemented"));
    }
}
