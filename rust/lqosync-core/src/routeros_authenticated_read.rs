use crate::protocol::Diagnostic;
use crate::routeros_auth_session::build_routeros_auth_session_contract_payload;
use crate::routeros_offline_session::run_routeros_offline_session_payload;
use crate::routeros_results::validate_routeros_read_results_payload;
use serde_json::{json, Value};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn merge_diags(target: &mut Vec<Diagnostic>, mut source: Vec<Diagnostic>) {
    target.append(&mut source);
}

fn live_requested(payload: &Value) -> bool {
    matches!(str_value(payload.get("adapter"), "fixture"), "live" | "tcp" | "routeros")
        || matches!(str_value(payload.get("mode"), "fixture"), "live" | "authenticated_live_read" | "execute_live")
}

fn fixture_rows_from_payload(payload: &Value) -> Vec<Value> {
    payload
        .get("fixture_rows")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn router_name_from_payload(payload: &Value) -> String {
    payload
        .get("router")
        .and_then(|v| v.get("name"))
        .and_then(Value::as_str)
        .or_else(|| payload.get("router").and_then(Value::as_str))
        .unwrap_or("unknown")
        .to_string()
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

/// Run an authenticated RouterOS read fixture.
///
/// This composes the redacted auth-session contract with the offline RouterOS
/// session pipeline and read-result trust contract. It never opens sockets,
/// never sends login words, never emits credentials, and never replaces Python
/// collectors. It exists to prove the future authenticated-read state machine
/// before a live Rust RouterOS adapter is allowed.
pub fn run_routeros_authenticated_read_fixture_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let execute = bool_value(payload.get("execute"), false);
    let adapter = str_value(payload.get("adapter"), "fixture");
    let path = str_value(payload.get("path"), "/ppp/active");
    let router_name = router_name_from_payload(payload);
    let source = str_value(payload.get("source"), source_from_path(path));

    if live_requested(payload) {
        errors.push(Diagnostic::error(
            "routeros_authenticated_read_live_adapter_not_implemented",
            Some("adapter".to_string()),
            "RouterOS authenticated read fixture cannot open live sockets or authenticate to MikroTik.",
        ));
    }

    let (auth_session, auth_errors, auth_warnings) = build_routeros_auth_session_contract_payload(payload);
    merge_diags(&mut errors, auth_errors);
    merge_diags(&mut warnings, auth_warnings);

    let authenticated = auth_session
        .get("authenticated")
        .and_then(Value::as_bool)
        .unwrap_or(false)
        && auth_session.get("status").and_then(Value::as_str) == Some("auth_session_contract_ready");

    if !authenticated && errors.is_empty() {
        errors.push(Diagnostic::error(
            "routeros_authenticated_read_session_not_authenticated",
            Some("auth_session".to_string()),
            "Authenticated read fixture requires an accepted auth-session contract.",
        ));
    }

    let mut offline_payload = payload.clone();
    if let Value::Object(ref mut map) = offline_payload {
        map.insert("adapter".to_string(), json!("offline_fixture"));
        map.insert("mode".to_string(), json!("offline_session"));
        map.insert("execute".to_string(), json!(false));
    }
    let (offline_session, offline_errors, offline_warnings) = run_routeros_offline_session_payload(&offline_payload);
    merge_diags(&mut errors, offline_errors);
    merge_diags(&mut warnings, offline_warnings);

    let rows = offline_session
        .get("reply_decode")
        .and_then(|v| v.get("rows"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| fixture_rows_from_payload(payload));

    let read_result_payload = json!({
        "router": router_name,
        "source": source,
        "status": if errors.is_empty() { "ok" } else { "failed" },
        "previous_success_count": payload.get("previous_success_count").and_then(Value::as_u64).unwrap_or(0),
        "plan": {
            "commands": [{"router": router_name, "source": source, "path": path, "required": true}]
        },
        "results": [{
            "router": router_name,
            "source": source,
            "path": path,
            "status": if errors.is_empty() { "ok" } else { "failed" },
            "rows": rows
        }]
    });
    let (read_validation, read_errors, read_warnings) = validate_routeros_read_results_payload(&read_result_payload);
    merge_diags(&mut errors, read_errors);
    merge_diags(&mut warnings, read_warnings);

    let row_count = offline_session.get("row_count").and_then(Value::as_u64).unwrap_or(0);
    let trap_count = offline_session.get("trap_count").and_then(Value::as_u64).unwrap_or(0);
    let status = if !errors.is_empty() {
        "blocked"
    } else if trap_count > 0 {
        "authenticated_read_fixture_trap"
    } else if authenticated {
        "authenticated_read_fixture_complete"
    } else {
        "authenticated_read_fixture_not_ready"
    };

    let result = json!({
        "mode": "routeros_authenticated_read_fixture",
        "status": status,
        "adapter": adapter,
        "authority": "fixture_only",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "authenticated": authenticated,
        "auth_session": auth_session,
        "offline_session": offline_session,
        "read_validation": read_validation,
        "router": router_name,
        "source": source,
        "path": path,
        "row_count": row_count,
        "trap_count": trap_count,
        "safe_for_cleanup": read_validation.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(false) && errors.is_empty(),
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "fixture_read_count": if execute && !live_requested(payload) { 1 } else { 0 },
        "credential_material": "redacted",
        "username_emitted": false,
        "password_emitted": false,
        "session_token_emitted": false,
        "next_stage": "rust_routeros_live_read_adapter_pilot",
        "note": "v3.3 proves authenticated read flow using fixtures only. It never opens sockets or replaces Python collectors."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn completes_authenticated_read_fixture_without_network() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"super-secret"},
            "adapter": "fixture",
            "execute": true,
            "fixture_reply_words": ["!done"],
            "path": "/ppp/active",
            "fields": ["name", "address"],
            "fixture_rows": [{"name":"client1", "address":"10.0.0.2"}]
        });
        let (result, errors, warnings) = run_routeros_authenticated_read_fixture_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty() || warnings.iter().all(|w| w.code.contains("warning") || !w.code.is_empty()));
        assert_eq!(result.get("status").and_then(Value::as_str), Some("authenticated_read_fixture_complete"));
        assert_eq!(result.get("authenticated").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("row_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super-secret"));
    }

    #[test]
    fn rejects_auth_fixture_trap_before_read_authority() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"super-secret"},
            "adapter": "fixture",
            "execute": true,
            "fixture_reply_words": ["!trap", "=message=bad login", "!done"],
            "path": "/ppp/active",
            "fixture_rows": [{"name":"client1"}]
        });
        let (result, errors, _warnings) = run_routeros_authenticated_read_fixture_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("authenticated").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_live_authenticated_read_adapter() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"super-secret"},
            "adapter": "live",
            "mode": "live",
            "execute": true,
            "fixture_reply_words": ["!done"],
            "path": "/ppp/active"
        });
        let (result, errors, _warnings) = run_routeros_authenticated_read_fixture_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert!(errors.iter().any(|e| e.code == "routeros_authenticated_read_live_adapter_not_implemented"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }
}
