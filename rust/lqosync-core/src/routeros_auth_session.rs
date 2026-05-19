use crate::protocol::Diagnostic;
use crate::routeros_auth_handshake::run_routeros_auth_handshake_payload;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn str_value<'a>(v: Option<&'a Value>, default: &'a str) -> &'a str {
    v.and_then(Value::as_str).unwrap_or(default)
}

fn router_field<'a>(payload: &'a Value, key: &str) -> Option<&'a str> {
    payload
        .get("router")
        .and_then(|v| v.get(key))
        .and_then(Value::as_str)
        .or_else(|| payload.get(key).and_then(Value::as_str))
}

fn make_session_id(router_name: &str, address: &str, auth_status: &str) -> String {
    let mut h = Sha256::new();
    h.update(router_name.as_bytes());
    h.update(b"|");
    h.update(address.as_bytes());
    h.update(b"|");
    h.update(auth_status.as_bytes());
    let digest = h.finalize();
    format!("ros-session-{}", hex::encode(&digest[..8]))
}

/// Build an authenticated RouterOS session contract from an auth handshake fixture.
///
/// This is not a live session. It intentionally emits a redacted, non-network
/// session state that future live adapters can compare against. It never opens
/// sockets, never emits credentials, and never stores passwords/tokens.
pub fn build_routeros_auth_session_contract_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let (handshake, handshake_errors, handshake_warnings) = run_routeros_auth_handshake_payload(payload);
    errors.extend(handshake_errors);
    warnings.extend(handshake_warnings);

    let execute = bool_value(payload.get("execute"), false);
    let mode = str_value(payload.get("mode"), "contract");
    let adapter = str_value(payload.get("adapter"), "fixture");
    let router_name = router_field(payload, "name").unwrap_or("unknown");
    let address = router_field(payload, "address").unwrap_or("");
    let auth_status = handshake.get("status").and_then(Value::as_str).unwrap_or("unknown");
    let authenticated = errors.is_empty() && auth_status == "auth_fixture_accepted";

    let live_requested = matches!(adapter, "live" | "tcp" | "routeros")
        || matches!(mode, "live" | "auth" | "execute_live");
    if live_requested {
        errors.push(Diagnostic::error(
            "routeros_auth_session_live_adapter_not_implemented",
            Some("adapter".to_string()),
            "RouterOS auth session contract is fixture-only in v3.2. Live authenticated sessions are not implemented.",
        ));
    }

    let allow_session_authority = bool_value(payload.pointer("/rust_core/allow_rust_routeros_session_state"), false)
        || bool_value(payload.get("allow_rust_routeros_session_state"), false);
    let session_authority = str_value(
        payload.pointer("/rust_core/routeros_session_authority"),
        str_value(payload.get("routeros_session_authority"), "contract_only"),
    );

    if execute && session_authority != "contract_only" && !allow_session_authority {
        errors.push(Diagnostic::error(
            "routeros_session_authority_not_allowed",
            Some("rust_core.allow_rust_routeros_session_state".to_string()),
            "RouterOS authenticated-session authority requires allow_rust_routeros_session_state=true.",
        ));
    }

    let status = if !errors.is_empty() {
        "blocked"
    } else if authenticated {
        "auth_session_contract_ready"
    } else {
        "auth_session_not_established"
    };

    let session_id = make_session_id(router_name, address, auth_status);
    let result = json!({
        "mode": "routeros_auth_session_contract",
        "status": status,
        "adapter": adapter,
        "router": router_name,
        "router_address_present": !address.is_empty(),
        "session_id": session_id,
        "session_state": if authenticated { "authenticated_fixture" } else { "not_authenticated" },
        "session_authority": session_authority,
        "allow_session_authority": allow_session_authority,
        "authenticated": authenticated,
        "auth_status": auth_status,
        "auth_handshake": handshake,
        "credential_material": "redacted",
        "username_emitted": false,
        "password_emitted": false,
        "session_token_emitted": false,
        "session_secret_emitted": false,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "live_session_supported": false,
        "full_rust_backend": false,
        "next_stage": "routeros_authenticated_read_fixture",
        "note": "v3.2 builds a redacted authenticated-session contract from fixture auth replies only. It never opens sockets, stores tokens, emits credentials, or replaces Python collectors."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn builds_authenticated_fixture_session_contract() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"super_secret_pw"},
            "adapter": "fixture",
            "execute": true,
            "fixture_reply_words": ["!done"]
        });
        let (result, errors, _warnings) = build_routeros_auth_session_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("auth_session_contract_ready"));
        assert_eq!(result.get("authenticated").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super_secret_pw"));
        assert!(!text.contains("admin"));
    }

    #[test]
    fn blocks_live_session_adapter() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"secret"},
            "adapter": "live",
            "execute": true,
            "fixture_reply_words": ["!done"]
        });
        let (result, errors, _warnings) = build_routeros_auth_session_contract_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert!(errors.iter().any(|e| e.code == "routeros_auth_session_live_adapter_not_implemented"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn rejected_auth_does_not_establish_session() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"secret"},
            "adapter": "fixture",
            "fixture_reply_words": ["!trap", "=message=invalid user", "!done"]
        });
        let (result, errors, _warnings) = build_routeros_auth_session_contract_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("auth_session_not_established"));
        assert_eq!(result.get("authenticated").and_then(Value::as_bool), Some(false));
    }
}
