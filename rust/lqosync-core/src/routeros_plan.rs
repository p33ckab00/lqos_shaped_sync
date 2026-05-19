use crate::protocol::Diagnostic;
use serde_json::{json, Value};

const PPP_ACTIVE_FIELDS: &[&str] = &["name", "address", "caller-id", "comment"];
const PPP_SECRET_FIELDS: &[&str] = &["name", "profile", "comment", "caller-id", "disabled", "inactive"];
const PPP_PROFILE_FIELDS: &[&str] = &["name", "comment", "rate-limit"];
const DHCP_LEASE_FIELDS: &[&str] = &["address", "mac-address", "host-name", "server", "status", "comment", "dynamic", "disabled"];
const DHCP_SERVER_FIELDS: &[&str] = &["name", "interface", "comment", "disabled", "lease-script"];
const HOTSPOT_ACTIVE_FIELDS: &[&str] = &["user", "address", "mac-address", "server", "uptime", "comment"];
const HOTSPOT_USER_FIELDS: &[&str] = &["name", "profile", "comment", "mac-address", "disabled"];
const HOTSPOT_PROFILE_FIELDS: &[&str] = &["name", "rate-limit", "comment"];

fn as_bool(value: Option<&Value>, default: bool) -> bool {
    value.and_then(Value::as_bool).unwrap_or(default)
}


fn fields(values: &[&str]) -> Value {
    Value::Array(values.iter().map(|v| Value::String((*v).to_string())).collect())
}

fn inc_source_count(map: &mut serde_json::Map<String, Value>, source: &str, by: u64) {
    let current = map.get(source).and_then(Value::as_u64).unwrap_or(0);
    map.insert(source.to_string(), json!(current + by));
}

fn command(router_name: &str, source: &str, path: &str, fields_value: Value, required: bool, purpose: &str, extra: Value) -> Value {
    let mut obj = serde_json::Map::new();
    obj.insert("router".to_string(), json!(router_name));
    obj.insert("source".to_string(), json!(source));
    obj.insert("path".to_string(), json!(path));
    obj.insert("fields".to_string(), fields_value);
    obj.insert("required".to_string(), json!(required));
    obj.insert("purpose".to_string(), json!(purpose));
    obj.insert("transport".to_string(), json!("routeros-api"));
    obj.insert("mode".to_string(), json!("plan_only"));
    if let Value::Object(extra_obj) = extra {
        for (k, v) in extra_obj {
            obj.insert(k, v);
        }
    }
    Value::Object(obj)
}

pub fn build_routeros_collector_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();

    let config = payload.get("config").unwrap_or(payload);
    let requested_router = payload.get("router").and_then(Value::as_str).unwrap_or("");
    let requested_source = payload.get("source").and_then(Value::as_str).unwrap_or("");
    let include_disabled = as_bool(payload.get("include_disabled_routers"), false);

    let routers_value = payload
        .get("routers")
        .or_else(|| config.get("routers"))
        .cloned()
        .unwrap_or_else(|| json!([]));
    let routers = routers_value.as_array().cloned().unwrap_or_default();

    let mut commands: Vec<Value> = Vec::new();
    let mut routers_seen = 0usize;
    let mut routers_planned = 0usize;
    let mut source_counts = serde_json::Map::new();

    for router in routers.iter().filter_map(Value::as_object) {
        routers_seen += 1;
        let router_name = router.get("name").and_then(Value::as_str).unwrap_or("Router");
        if !requested_router.is_empty() && requested_router != router_name {
            continue;
        }
        let enabled = as_bool(router.get("enabled"), true);
        if !enabled && !include_disabled {
            continue;
        }
        routers_planned += 1;

        let pppoe = router.get("pppoe").and_then(Value::as_object);
        let pppoe_enabled = pppoe.map(|v| as_bool(v.get("enabled"), false)).unwrap_or(false);
        if pppoe_enabled && (requested_source.is_empty() || requested_source == "pppoe" || requested_source == "PPP") {
            commands.push(command(router_name, "pppoe", "/ppp/active", fields(PPP_ACTIVE_FIELDS), true, "Read active PPPoE sessions.", json!({"trust_role":"active_presence"})));
            commands.push(command(router_name, "pppoe", "/ppp/secret", fields(PPP_SECRET_FIELDS), true, "Read PPPoE secrets for profile and disabled/inactive state.", json!({"trust_role":"identity_profile"})));
            commands.push(command(router_name, "pppoe", "/ppp/profile", fields(PPP_PROFILE_FIELDS), true, "Read PPPoE profiles for rate-limit fallback.", json!({"trust_role":"speed_profile"})));
            inc_source_count(&mut source_counts, "pppoe", 3);
        }

        let dhcp = router.get("dhcp").and_then(Value::as_object);
        let dhcp_enabled = dhcp.map(|v| as_bool(v.get("enabled"), false)).unwrap_or(false);
        if dhcp_enabled && (requested_source.is_empty() || requested_source == "dhcp" || requested_source == "DHCP") {
            let servers = dhcp.and_then(|d| d.get("servers")).and_then(Value::as_array).cloned().unwrap_or_default();
            let enabled_servers: Vec<String> = servers.iter()
                .filter_map(Value::as_object)
                .filter(|s| as_bool(s.get("enabled"), true))
                .filter_map(|s| s.get("name").and_then(Value::as_str).map(|v| v.to_string()))
                .collect();
            commands.push(command(router_name, "dhcp", "/ip/dhcp-server/lease", fields(DHCP_LEASE_FIELDS), true, "Read DHCP leases for IP/MAC/hostname/server mapping.", json!({"trust_role":"lease_presence", "server_filter": enabled_servers})));
            let read_server_metadata = config.get("collector")
                .and_then(|c| c.get("dhcp"))
                .map(|d| as_bool(d.get("read_server_metadata"), true))
                .unwrap_or(true);
            if read_server_metadata {
                commands.push(command(router_name, "dhcp", "/ip/dhcp-server", fields(DHCP_SERVER_FIELDS), false, "Read DHCP server metadata for speed/comment context.", json!({"trust_role":"source_metadata"})));
                inc_source_count(&mut source_counts, "dhcp", 2);
            } else {
                inc_source_count(&mut source_counts, "dhcp", 1);
            }
        }

        let hotspot = router.get("hotspot").and_then(Value::as_object);
        let hotspot_enabled = hotspot.map(|v| as_bool(v.get("enabled"), false)).unwrap_or(false);
        if hotspot_enabled && (requested_source.is_empty() || requested_source == "hotspot" || requested_source == "HS") {
            commands.push(command(router_name, "hotspot", "/ip/hotspot/active", fields(HOTSPOT_ACTIVE_FIELDS), true, "Read active Hotspot sessions.", json!({"trust_role":"active_presence"})));
            commands.push(command(router_name, "hotspot", "/ip/hotspot/user", fields(HOTSPOT_USER_FIELDS), false, "Read Hotspot users for profile/comment speed hints.", json!({"trust_role":"identity_profile"})));
            commands.push(command(router_name, "hotspot", "/ip/hotspot/user/profile", fields(HOTSPOT_PROFILE_FIELDS), false, "Read Hotspot profiles for rate-limit fallback.", json!({"trust_role":"speed_profile"})));
            inc_source_count(&mut source_counts, "hotspot", 3);
        }
    }

    if routers_seen == 0 {
        warnings.push(Diagnostic::warning(
            "routeros_plan_no_routers",
            Some("config.routers".to_string()),
            "No routers were present in the config, so the RouterOS collector plan is empty.",
        ));
    } else if routers_planned == 0 {
        warnings.push(Diagnostic::warning(
            "routeros_plan_no_enabled_router_match",
            Some("config.routers".to_string()),
            "No enabled routers matched the requested RouterOS collector plan filter.",
        ));
    }
    if commands.is_empty() {
        warnings.push(Diagnostic::warning(
            "routeros_plan_no_enabled_sources",
            Some("config.routers".to_string()),
            "No enabled PPPoE, DHCP, or Hotspot sources matched the requested RouterOS collector plan.",
        ));
    }

    let required_count = commands.iter().filter(|c| c.get("required").and_then(Value::as_bool).unwrap_or(false)).count();
    let result = json!({
        "mode": "plan_only",
        "authority": "none",
        "status": if commands.is_empty() { "empty" } else { "ready" },
        "router_count": routers_planned,
        "command_count": commands.len(),
        "required_command_count": required_count,
        "source_counts": Value::Object(source_counts),
        "commands": commands,
        "next_stage": "rust_routeros_transport_shadow",
        "full_rust_backend": false,
        "note": "This is a deterministic RouterOS read plan only. It does not open RouterOS connections or replace Python collectors."
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn builds_pppoe_dhcp_routeros_plan() {
        let payload = json!({
            "config": {
                "collector": {"dhcp": {"read_server_metadata": true}},
                "routers": [{
                    "name": "RB5009",
                    "enabled": true,
                    "pppoe": {"enabled": true},
                    "dhcp": {"enabled": true, "servers": [{"name":"LAN", "enabled":true}]},
                    "hotspot": {"enabled": false}
                }]
            }
        });
        let (result, errors, warnings) = build_routeros_collector_plan_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
        assert_eq!(result.get("command_count").and_then(Value::as_u64), Some(5));
        let commands = result.get("commands").and_then(Value::as_array).unwrap();
        assert!(commands.iter().any(|c| c.get("path").and_then(Value::as_str) == Some("/ppp/active")));
        assert!(commands.iter().any(|c| c.get("path").and_then(Value::as_str) == Some("/ip/dhcp-server/lease")));
    }

    #[test]
    fn warns_when_no_sources_enabled() {
        let payload = json!({"config": {"routers": [{"name":"RB5009", "enabled": true}]}});
        let (result, errors, warnings) = build_routeros_collector_plan_payload(&payload);
        assert!(errors.is_empty());
        assert!(!warnings.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("empty"));
    }
}
