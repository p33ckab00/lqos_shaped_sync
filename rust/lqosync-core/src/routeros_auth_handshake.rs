use crate::protocol::Diagnostic;
use crate::routeros_api_reply::decode_routeros_api_reply_payload;
use crate::routeros_auth_plan::build_routeros_auth_plan_payload;
use serde_json::{json, Value};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn collect_reply_words(payload: &Value) -> Vec<String> {
    if let Some(words) = payload.get("fixture_reply_words").and_then(Value::as_array) {
        return words.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect();
    }
    if let Some(words) = payload.get("reply_words").and_then(Value::as_array) {
        return words.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect();
    }
    if let Some(text) = payload.get("fixture_reply_text").and_then(Value::as_str) {
        return text.lines().map(str::trim).filter(|s| !s.is_empty()).map(|s| s.to_string()).collect();
    }
    vec!["!done".to_string()]
}

fn fixture_adapter(payload: &Value) -> bool {
    matches!(
        str_value(payload.get("adapter"), "fixture"),
        "fixture" | "offline" | "offline_fixture" | "auth_fixture"
    )
}

fn wants_live(payload: &Value) -> bool {
    matches!(str_value(payload.get("adapter"), "fixture"), "live" | "tcp" | "routeros")
        || matches!(str_value(payload.get("mode"), "fixture"), "live" | "auth" | "execute_live")
}

/// Run a RouterOS authentication handshake fixture.
///
/// This operation models the future auth request/reply state machine without
/// opening sockets, sending credentials, or authenticating to MikroTik. It is
/// intentionally fixture-only: the login words are redacted, reply words are
/// decoded through the offline reply parser, and any live adapter request is
/// blocked.
pub fn run_routeros_auth_handshake_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    // Validate that a future auth adapter would have enough config material,
    // but force execute=false so the plan does not raise the not-implemented
    // live adapter blocker for this offline fixture operation.
    let mut plan_payload = payload.clone();
    if let Some(obj) = plan_payload.as_object_mut() {
        obj.insert("execute".to_string(), Value::Bool(false));
        obj.insert("mode".to_string(), Value::String("auth_plan".to_string()));
    }
    let (auth_plan, plan_errors, plan_warnings) = build_routeros_auth_plan_payload(&plan_payload);
    errors.extend(plan_errors);
    warnings.extend(plan_warnings);

    let execute = bool_value(payload.get("execute"), false);
    let adapter_is_fixture = fixture_adapter(payload);
    let live_requested = wants_live(payload);

    if live_requested || !adapter_is_fixture {
        errors.push(Diagnostic::error(
            "routeros_auth_handshake_live_adapter_not_implemented",
            Some("adapter".to_string()),
            "RouterOS auth handshake is fixture-only in v3.1. Live authentication is not implemented.",
        ));
    }

    let reply_words = collect_reply_words(payload);
    let (reply, reply_errors, reply_warnings) = decode_routeros_api_reply_payload(&json!({
        "words": reply_words,
        "adapter": "offline_words",
        "mode": "decode_only",
        "execute": false
    }));
    errors.extend(reply_errors);
    warnings.extend(reply_warnings);

    let reply_status = reply.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let trap_count = reply.get("trap_count").and_then(Value::as_u64).unwrap_or(0);
    let done_count = reply.get("done_count").and_then(Value::as_u64).unwrap_or(0);
    let accepted = errors.is_empty() && trap_count == 0 && done_count > 0;
    let status = if !errors.is_empty() {
        "blocked"
    } else if accepted {
        "auth_fixture_accepted"
    } else if trap_count > 0 {
        "auth_fixture_rejected"
    } else {
        "auth_fixture_incomplete"
    };

    let result = json!({
        "mode": "routeros_auth_handshake_fixture",
        "status": status,
        "adapter": str_value(payload.get("adapter"), "fixture"),
        "execute_requested": execute,
        "fixture_executed": adapter_is_fixture && !live_requested,
        "router": auth_plan.get("router").cloned().unwrap_or_else(|| json!("unknown")),
        "auth_plan_status": auth_plan.get("status").cloned().unwrap_or_else(|| json!("unknown")),
        "request_words_redacted": ["/login", "=name=<redacted>", "=password=<redacted>"],
        "credential_material": "redacted",
        "username_emitted": false,
        "password_emitted": false,
        "login_sentence_emitted": false,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "fixture_handshake_count": if adapter_is_fixture && !live_requested { 1 } else { 0 },
        "reply_status": reply_status,
        "reply_done_count": done_count,
        "reply_trap_count": trap_count,
        "reply_row_count": reply.get("row_count").and_then(Value::as_u64).unwrap_or(0),
        "reply": reply,
        "live_auth_supported": false,
        "full_rust_backend": false,
        "next_stage": "routeros_readonly_auth_adapter_pilot",
        "note": "v3.1 models the RouterOS authentication handshake using fixture reply words only. It never opens sockets, emits credentials, or authenticates to MikroTik."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn accepts_fixture_done_without_network_or_credentials() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"super_secret_pw"},
            "adapter": "fixture",
            "execute": true,
            "fixture_reply_words": ["!done"]
        });
        let (result, errors, _warnings) = run_routeros_auth_handshake_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("auth_fixture_accepted"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("authentication_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super_secret_pw"));
        assert!(!text.contains("admin"));
    }

    #[test]
    fn reports_fixture_trap_as_rejected() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"secret"},
            "adapter": "fixture",
            "fixture_reply_words": ["!trap", "=message=invalid user name or password", "!done"]
        });
        let (result, errors, _warnings) = run_routeros_auth_handshake_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("auth_fixture_rejected"));
        assert_eq!(result.get("reply_trap_count").and_then(Value::as_u64), Some(1));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("secret"));
    }

    #[test]
    fn blocks_live_auth_handshake_adapter() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"secret"},
            "adapter": "live",
            "execute": true,
            "fixture_reply_words": ["!done"]
        });
        let (result, errors, _warnings) = run_routeros_auth_handshake_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert!(errors.iter().any(|e| e.code == "routeros_auth_handshake_live_adapter_not_implemented"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }
}
