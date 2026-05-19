use crate::protocol::Diagnostic;
use serde_json::{json, Value};

fn config<'a>(payload: &'a Value) -> &'a Value {
    payload.get("config").unwrap_or(payload)
}

fn rust_core<'a>(payload: &'a Value) -> &'a Value {
    config(payload).get("rust_core").unwrap_or(&Value::Null)
}

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn string_value(v: Option<&Value>, default: &str) -> String {
    v.and_then(Value::as_str).unwrap_or(default).to_string()
}

fn wants_execute(payload: &Value) -> bool {
    bool_value(payload.get("execute"), false)
        || matches!(payload.get("mode").and_then(Value::as_str).unwrap_or("rehearsal"), "auth" | "live" | "execute")
}

fn selected_router(payload: &Value) -> Value {
    if let Some(router) = payload.get("router").filter(|v| v.is_object()) {
        return router.clone();
    }
    let router_name = payload.get("router").and_then(Value::as_str).unwrap_or("");
    let routers = config(payload).get("routers").and_then(Value::as_array);
    if let Some(routers) = routers {
        for router in routers {
            if !router.get("enabled").and_then(Value::as_bool).unwrap_or(true) {
                continue;
            }
            if router_name.is_empty() || router.get("name").and_then(Value::as_str).unwrap_or("") == router_name {
                return router.clone();
            }
        }
    }
    json!({})
}

fn authority(payload: &Value) -> String {
    string_value(
        payload
            .get("routeros_transport_authority")
            .or_else(|| rust_core(payload).get("routeros_transport_authority")),
        "plan_only",
    )
}

fn allow_credentials(payload: &Value) -> bool {
    bool_value(payload.get("allow_credentials"), false)
        || bool_value(rust_core(payload).get("allow_rust_routeros_credentials"), false)
}

fn allow_auth_pilot(payload: &Value) -> bool {
    bool_value(payload.get("allow_auth_pilot"), false)
        || bool_value(rust_core(payload).get("routeros_auth_pilot"), false)
}

/// Build a redacted RouterOS authentication plan.
///
/// This is not an authentication adapter. It validates that the future Rust
/// authentication stage has enough information and safety gates, while never
/// emitting password/API key material and never opening sockets.
pub fn build_routeros_auth_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let warnings: Vec<Diagnostic> = Vec::new();

    let router = selected_router(payload);
    let router_name = router.get("name").and_then(Value::as_str).unwrap_or("unknown");
    let address_present = payload.get("address").and_then(Value::as_str).map(|s| !s.trim().is_empty()).unwrap_or(false)
        || router.get("address").and_then(Value::as_str).map(|s| !s.trim().is_empty()).unwrap_or(false);
    let username_present = payload.get("username").and_then(Value::as_str).map(|s| !s.trim().is_empty()).unwrap_or(false)
        || router.get("username").and_then(Value::as_str).map(|s| !s.trim().is_empty()).unwrap_or(false);
    let password_present = payload.get("password").and_then(Value::as_str).map(|s| !s.is_empty()).unwrap_or(false)
        || router.get("password").and_then(Value::as_str).map(|s| !s.is_empty()).unwrap_or(false);
    let port = payload
        .get("port")
        .and_then(Value::as_u64)
        .or_else(|| router.get("port").and_then(Value::as_u64))
        .unwrap_or(8728);
    let execute = wants_execute(payload);
    let credential_allowed = allow_credentials(payload);
    let auth_pilot_allowed = allow_auth_pilot(payload);
    let transport_authority = authority(payload);

    if !address_present {
        errors.push(Diagnostic::error(
            "routeros_auth_address_missing",
            Some("router.address".to_string()),
            "RouterOS authentication plan requires a router address before a future live auth adapter can run.",
        ));
    }
    if !username_present {
        errors.push(Diagnostic::error(
            "routeros_auth_username_missing",
            Some("router.username".to_string()),
            "RouterOS authentication plan requires a username.",
        ));
    }
    if !password_present {
        errors.push(Diagnostic::error(
            "routeros_auth_password_missing",
            Some("router.password".to_string()),
            "RouterOS authentication plan requires password material, but the value is never emitted by Rust.",
        ));
    }
    if port == 0 {
        errors.push(Diagnostic::error(
            "routeros_auth_port_invalid",
            Some("router.port".to_string()),
            "RouterOS authentication plan requires a non-zero TCP port.",
        ));
    }

    if execute && !credential_allowed {
        errors.push(Diagnostic::error(
            "routeros_credentials_not_allowed",
            Some("rust_core.allow_rust_routeros_credentials".to_string()),
            "Rust RouterOS authentication pilot was requested, but credential access is disabled.",
        ));
    }
    if execute && !auth_pilot_allowed {
        errors.push(Diagnostic::error(
            "routeros_auth_pilot_not_allowed",
            Some("rust_core.routeros_auth_pilot".to_string()),
            "Rust RouterOS authentication pilot was requested, but routeros_auth_pilot is disabled.",
        ));
    }
    if execute && transport_authority != "auth_pilot" && transport_authority != "live_read_pilot" {
        errors.push(Diagnostic::error(
            "routeros_auth_authority_not_enabled",
            Some("rust_core.routeros_transport_authority".to_string()),
            "Rust RouterOS authentication pilot requires routeros_transport_authority=auth_pilot or live_read_pilot.",
        ));
    }
    if execute && errors.is_empty() {
        errors.push(Diagnostic::error(
            "routeros_auth_adapter_not_implemented",
            Some("routeros_auth_plan".to_string()),
            "Rust RouterOS authentication adapter is not implemented yet. This operation only builds a redacted auth plan.",
        ));
    }

    let status = if !errors.is_empty() {
        "blocked"
    } else if execute {
        "auth_adapter_pending"
    } else {
        "auth_plan_ready"
    };

    let result = json!({
        "mode": if execute { "auth_pilot" } else { "auth_plan" },
        "status": status,
        "router": router_name,
        "address_redacted": if address_present { "configured" } else { "missing" },
        "port": port,
        "username_present": username_present,
        "password_present": password_present,
        "credential_material": "redacted",
        "password_emitted": false,
        "login_sentence_emitted": false,
        "routeros_transport_authority": transport_authority,
        "allow_credentials": credential_allowed,
        "auth_pilot_allowed": auth_pilot_allowed,
        "connection_attempt_count": 0,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "live_auth_supported": false,
        "full_rust_backend": false,
        "next_stage": "routeros_auth_adapter_pilot",
        "note": "This operation is a redacted authentication plan only. It does not open sockets, emit passwords, authenticate, or replace Python collectors."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builds_redacted_auth_plan_without_execution() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "port":8728, "username":"admin", "password":"super_private_pw_123"},
            "execute": false
        });
        let (result, errors, _warnings) = build_routeros_auth_plan_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("auth_plan_ready"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("authentication_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super_private_pw_123"));
        assert!(!text.contains("\"password\""));
    }

    #[test]
    fn blocks_execute_without_credential_authority() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"secret"},
            "execute": true,
            "config": {"rust_core": {"routeros_transport_authority":"plan_only"}}
        });
        let (result, errors, _warnings) = build_routeros_auth_plan_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert!(errors.iter().any(|e| e.code == "routeros_credentials_not_allowed"));
    }

    #[test]
    fn blocks_even_when_gates_enabled_until_adapter_exists() {
        let payload = json!({
            "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"secret"},
            "execute": true,
            "config": {"rust_core": {
                "allow_rust_routeros_credentials": true,
                "routeros_auth_pilot": true,
                "routeros_transport_authority":"auth_pilot"
            }}
        });
        let (result, errors, _warnings) = build_routeros_auth_plan_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert!(errors.iter().any(|e| e.code == "routeros_auth_adapter_not_implemented"));
    }
}
