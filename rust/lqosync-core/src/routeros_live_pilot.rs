use crate::protocol::Diagnostic;
use crate::routeros_plan::build_routeros_collector_plan_payload;
use crate::routeros_transport::build_routeros_transport_session_payload;
use serde_json::{json, Value};

fn as_bool(value: Option<&Value>, default: bool) -> bool {
    value.and_then(Value::as_bool).unwrap_or(default)
}

fn as_str<'a>(value: Option<&'a Value>, default: &'a str) -> &'a str {
    value.and_then(Value::as_str).unwrap_or(default)
}

fn command_matches(cmd: &Value, router: &str, source: &str, path: &str) -> bool {
    (router.is_empty() || cmd.get("router").and_then(Value::as_str) == Some(router))
        && (source.is_empty() || cmd.get("source").and_then(Value::as_str) == Some(source))
        && (path.is_empty() || cmd.get("path").and_then(Value::as_str) == Some(path))
}

/// Build a gated live-read pilot request for a single RouterOS command.
///
/// This is intentionally still non-network in v2.3. It selects one command from
/// the deterministic RouterOS read plan, verifies the authority gates, redacts
/// all credential material, and returns a pilot contract for a future transport
/// adapter. It never opens a socket and never sends RouterOS credentials.
pub fn build_routeros_live_read_pilot_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let config = payload.get("config").cloned().unwrap_or_else(|| json!({}));
    let rust_core = config.get("rust_core").cloned().unwrap_or_else(|| json!({}));
    let router = as_str(payload.get("router"), "");
    let source = as_str(payload.get("source"), "");
    let path = as_str(payload.get("path"), "");
    let execute = as_bool(payload.get("execute"), false);
    let mode = as_str(payload.get("mode"), "rehearsal");

    let pilot_enabled = as_bool(
        payload.get("pilot_enabled"),
        as_bool(rust_core.get("routeros_live_read_pilot"), false),
    );
    let allow_live_reads = as_bool(
        payload.get("allow_live_reads"),
        as_bool(rust_core.get("allow_rust_routeros_live_reads"), false),
    );
    let allow_credentials = as_bool(
        payload.get("allow_credentials"),
        as_bool(rust_core.get("allow_rust_routeros_credentials"), false),
    );
    let transport_authority = as_str(rust_core.get("routeros_transport_authority"), "plan_only");
    let live_timeout_seconds = rust_core
        .get("routeros_live_read_timeout_seconds")
        .and_then(Value::as_u64)
        .unwrap_or(5);

    let plan_payload = json!({
        "config": config,
        "router": router,
        "source": source,
        "include_disabled_routers": false,
    });
    let (plan, plan_errors, plan_warnings) = build_routeros_collector_plan_payload(&plan_payload);
    errors.extend(plan_errors);
    warnings.extend(plan_warnings);
    let commands = plan.get("commands").and_then(Value::as_array).cloned().unwrap_or_default();
    let selected = commands.iter().find(|cmd| command_matches(cmd, router, source, path)).cloned();

    if selected.is_none() {
        errors.push(Diagnostic::error(
            "routeros_live_read_no_planned_command",
            Some("routeros_live_read_pilot".to_string()),
            "No RouterOS read command matched the requested router/source/path pilot selection.",
        ));
    }

    let transport_payload = json!({
        "config": plan_payload.get("config").cloned().unwrap_or_else(|| json!({})),
        "router": router,
        "source": source,
        "mode": "rehearsal",
        "execute": false,
    });
    let (transport, transport_errors, transport_warnings) = build_routeros_transport_session_payload(&transport_payload);
    errors.extend(transport_errors);
    warnings.extend(transport_warnings);

    let wants_live = execute || mode == "live";
    if wants_live && !pilot_enabled {
        errors.push(Diagnostic::error(
            "routeros_live_read_pilot_disabled",
            Some("rust_core.routeros_live_read_pilot".to_string()),
            "Rust RouterOS live-read pilot is disabled. Keep this disabled until transport rehearsals and parity reports are clean.",
        ));
    }
    if wants_live && !allow_live_reads {
        errors.push(Diagnostic::error(
            "routeros_live_reads_not_allowed",
            Some("rust_core.allow_rust_routeros_live_reads".to_string()),
            "Rust RouterOS live reads are not allowed by configuration.",
        ));
    }
    if wants_live && !allow_credentials {
        errors.push(Diagnostic::error(
            "routeros_credentials_not_allowed",
            Some("rust_core.allow_rust_routeros_credentials".to_string()),
            "Rust RouterOS credential access is not allowed by configuration.",
        ));
    }
    if wants_live && transport_authority != "live_read_pilot" {
        errors.push(Diagnostic::error(
            "routeros_transport_authority_not_live_read_pilot",
            Some("rust_core.routeros_transport_authority".to_string()),
            "Rust RouterOS transport authority must be live_read_pilot before any live-read pilot can be attempted.",
        ));
    }
    if wants_live && pilot_enabled && allow_live_reads && allow_credentials && transport_authority == "live_read_pilot" {
        errors.push(Diagnostic::error(
            "routeros_live_transport_adapter_not_implemented",
            Some("routeros_live_read_pilot".to_string()),
            "Live RouterOS socket transport is still not implemented in Rust. v2.3 only builds and gates the pilot request contract.",
        ));
    }

    if !wants_live && pilot_enabled {
        warnings.push(Diagnostic::warning(
            "routeros_live_read_pilot_rehearsal_only",
            Some("routeros_live_read_pilot".to_string()),
            "RouterOS live-read pilot is enabled, but this request is rehearsal-only and will not connect to MikroTik.",
        ));
    }

    let status = if !errors.is_empty() {
        "blocked"
    } else if selected.is_some() {
        "pilot_contract_ready"
    } else {
        "empty"
    };

    let selected_public = selected.map(|cmd| json!({
        "router": cmd.get("router").cloned().unwrap_or_else(|| json!("unknown")),
        "source": cmd.get("source").cloned().unwrap_or_else(|| json!("unknown")),
        "path": cmd.get("path").cloned().unwrap_or_else(|| json!("")),
        "fields": cmd.get("fields").cloned().unwrap_or_else(|| json!([])),
        "required": cmd.get("required").cloned().unwrap_or_else(|| json!(false)),
        "purpose": cmd.get("purpose").cloned().unwrap_or_else(|| json!("")),
        "trust_role": cmd.get("trust_role").cloned().unwrap_or_else(|| json!("unknown")),
    }));

    let result = json!({
        "mode": "routeros_live_read_pilot_contract",
        "status": status,
        "authority": "none",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "execute_requested": execute,
        "connection_attempt_count": 0,
        "pilot_enabled": pilot_enabled,
        "allow_live_reads": allow_live_reads,
        "allow_credentials": allow_credentials,
        "routeros_transport_authority": transport_authority,
        "timeout_seconds": live_timeout_seconds,
        "selected_command": selected_public,
        "transport_session": transport,
        "credential_material": "redacted",
        "next_stage": "rust_routeros_readonly_transport_adapter",
        "note": "v2.3 builds a gated live-read pilot contract only. It does not open RouterOS sockets or consume credentials."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rehearses_live_read_pilot_without_connections() {
        let payload = json!({"router":"R1","source":"pppoe","config":{"routers":[{"name":"R1","enabled":true,"address":"10.0.0.1","username":"admin","password":"super_private_pw_123","pppoe":{"enabled":true}}]}});
        let (result, errors, _warnings) = build_routeros_live_read_pilot_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("pilot_contract_ready"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super_private_pw_123"));
        assert!(!text.contains("\"password\""));
    }

    #[test]
    fn blocks_live_execution_without_gates() {
        let payload = json!({"mode":"live","execute":true,"router":"R1","source":"pppoe","config":{"routers":[{"name":"R1","enabled":true,"address":"10.0.0.1","username":"admin","password":"secret","pppoe":{"enabled":true}}]}});
        let (result, errors, _warnings) = build_routeros_live_read_pilot_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn blocks_even_when_gates_enabled_until_adapter_exists() {
        let payload = json!({
            "mode":"live",
            "execute":true,
            "router":"R1",
            "source":"pppoe",
            "config":{
                "rust_core":{
                    "routeros_live_read_pilot":true,
                    "allow_rust_routeros_live_reads":true,
                    "allow_rust_routeros_credentials":true,
                    "routeros_transport_authority":"live_read_pilot"
                },
                "routers":[{"name":"R1","enabled":true,"address":"10.0.0.1","username":"admin","password":"secret","pppoe":{"enabled":true}}]
            }
        });
        let (result, errors, _warnings) = build_routeros_live_read_pilot_payload(&payload);
        assert!(!errors.is_empty());
        assert!(errors.iter().any(|e| e.code == "routeros_live_transport_adapter_not_implemented"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }
}
