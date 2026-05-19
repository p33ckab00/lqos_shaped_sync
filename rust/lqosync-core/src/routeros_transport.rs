use crate::protocol::Diagnostic;
use crate::routeros_plan::build_routeros_collector_plan_payload;
use serde_json::{json, Value};

fn as_bool(value: Option<&Value>, default: bool) -> bool {
    value.and_then(Value::as_bool).unwrap_or(default)
}

fn as_str<'a>(value: Option<&'a Value>, default: &'a str) -> &'a str {
    value.and_then(Value::as_str).unwrap_or(default)
}

fn as_u16(value: Option<&Value>, default: u16) -> u16 {
    value.and_then(Value::as_u64).and_then(|v| u16::try_from(v).ok()).unwrap_or(default)
}

fn source_enabled(router: &Value, source: &str) -> bool {
    router.get(source).and_then(|v| v.get("enabled")).and_then(Value::as_bool).unwrap_or(false)
}

fn command_count_for_router(commands: &[Value], router_name: &str) -> usize {
    commands.iter().filter(|cmd| cmd.get("router").and_then(Value::as_str) == Some(router_name)).count()
}

/// Build a non-network RouterOS transport session rehearsal.
///
/// This intentionally does not open sockets or use RouterOS credentials. It is
/// the contract layer before a future Rust RouterOS transport implementation.
pub fn build_routeros_transport_session_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let config = payload.get("config").cloned().unwrap_or_else(|| json!({}));
    let rust_core = config.get("rust_core").cloned().unwrap_or_else(|| json!({}));
    let mode = as_str(payload.get("mode"), "rehearsal");
    let execute = as_bool(payload.get("execute"), false);
    let allow_live_reads = as_bool(payload.get("allow_live_reads"), as_bool(rust_core.get("allow_rust_routeros_live_reads"), false));
    let allow_credentials = as_bool(payload.get("allow_credentials"), as_bool(rust_core.get("allow_rust_routeros_credentials"), false));
    let transport_authority = as_str(rust_core.get("routeros_transport_authority"), "plan_only");

    let plan_payload = json!({
        "config": config,
        "router": payload.get("router").and_then(Value::as_str).unwrap_or(""),
        "source": payload.get("source").and_then(Value::as_str).unwrap_or(""),
        "include_disabled_routers": as_bool(payload.get("include_disabled_routers"), false),
    });
    let (plan, plan_errors, plan_warnings) = build_routeros_collector_plan_payload(&plan_payload);
    errors.extend(plan_errors);
    warnings.extend(plan_warnings);

    let commands = plan.get("commands").and_then(Value::as_array).cloned().unwrap_or_default();
    let routers = plan_payload.get("config").and_then(|c| c.get("routers")).and_then(Value::as_array).cloned().unwrap_or_default();
    let mut sessions: Vec<Value> = Vec::new();
    let mut router_count = 0usize;
    let mut credential_count = 0usize;

    for router in routers {
        if router.get("enabled").and_then(Value::as_bool).unwrap_or(true) == false && !as_bool(payload.get("include_disabled_routers"), false) {
            continue;
        }
        let name = as_str(router.get("name"), "unknown").to_string();
        let count = command_count_for_router(&commands, &name);
        if count == 0 {
            continue;
        }
        router_count += 1;
        let username_present = router.get("username").and_then(Value::as_str).map(|v| !v.is_empty()).unwrap_or(false);
        let password_present = router.get("password").and_then(Value::as_str).map(|v| !v.is_empty()).unwrap_or(false);
        if username_present || password_present { credential_count += 1; }
        sessions.push(json!({
            "router": name,
            "address_present": router.get("address").and_then(Value::as_str).map(|v| !v.is_empty()).unwrap_or(false),
            "address_redacted": router.get("address").and_then(Value::as_str).map(|_| "configured").unwrap_or("missing"),
            "port": as_u16(router.get("port"), 8728),
            "username_present": username_present,
            "password_present": password_present,
            "credential_material": "redacted",
            "sources": {
                "pppoe": source_enabled(&router, "pppoe"),
                "dhcp": source_enabled(&router, "dhcp"),
                "hotspot": source_enabled(&router, "hotspot")
            },
            "command_count": count,
            "status": "planned_not_connected",
            "connection_attempted": false,
        }));
    }

    let wants_live = execute || mode == "live" || transport_authority == "live_read_pilot";
    if wants_live {
        errors.push(Diagnostic::error(
            "routeros_live_transport_not_implemented",
            Some("rust_core.routeros_transport_authority".to_string()),
            "Live Rust RouterOS transport is not implemented in this release. This operation only rehearses sessions and redacts credentials.",
        ));
    }
    if allow_live_reads && !allow_credentials {
        warnings.push(Diagnostic::warning(
            "routeros_credentials_not_allowed",
            Some("rust_core.allow_rust_routeros_credentials".to_string()),
            "Rust live reads were requested but credential access is not allowed; no live transport can be attempted.",
        ));
    }

    let status = if !errors.is_empty() {
        "blocked"
    } else if commands.is_empty() {
        "empty"
    } else {
        "ready_for_future_transport"
    };

    let result = json!({
        "mode": "transport_rehearsal",
        "status": status,
        "authority": "none",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "connection_attempt_count": 0,
        "allow_live_reads": allow_live_reads,
        "allow_credentials": allow_credentials,
        "routeros_transport_authority": transport_authority,
        "router_count": router_count,
        "credential_router_count": credential_count,
        "command_count": commands.len(),
        "sessions": sessions,
        "plan": plan,
        "next_stage": "rust_routeros_transport_client_pilot",
        "note": "This is a RouterOS transport-session rehearsal only. Rust does not connect to MikroTik or consume credentials in this release."
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rehearses_routeros_transport_without_connections() {
        let payload = json!({"config":{"routers":[{"name":"R1","enabled":true,"address":"10.0.0.1","username":"admin","password":"secret","pppoe":{"enabled":true}}]}});
        let (result, errors, _warnings) = build_routeros_transport_session_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("status").and_then(Value::as_str), Some("ready_for_future_transport"));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("secret"));
    }

    #[test]
    fn blocks_live_transport_attempts() {
        let payload = json!({"mode":"live","execute":true,"config":{"rust_core":{"allow_rust_routeros_live_reads":true,"allow_rust_routeros_credentials":true},"routers":[{"name":"R1","enabled":true,"address":"10.0.0.1","username":"admin","password":"secret","pppoe":{"enabled":true}}]}});
        let (result, errors, _warnings) = build_routeros_transport_session_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
