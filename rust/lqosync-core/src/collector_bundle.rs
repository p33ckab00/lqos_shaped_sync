use crate::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit, BandwidthPair};
use crate::protocol::{Diagnostic, Severity};
use crate::shaped_devices::{ShapedDeviceRow, FIELDNAMES};
use regex::Regex;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};

fn sval(value: &Value, key: &str) -> String {
    match value.get(key) {
        Some(Value::String(s)) => s.trim().to_string(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Bool(b)) => b.to_string(),
        _ => String::new(),
    }
}

fn obj<'a>(value: &'a Value, key: &str) -> Option<&'a Value> {
    value.get(key).filter(|v| v.is_object())
}

fn arr<'a>(value: &'a Value, key: &str) -> Vec<&'a Value> {
    value.get(key).and_then(Value::as_array).map(|items| items.iter().collect()).unwrap_or_default()
}

fn boolish(value: &Value, key: &str) -> bool {
    match value.get(key) {
        Some(Value::Bool(b)) => *b,
        Some(Value::String(s)) => matches!(s.trim().to_ascii_lowercase().as_str(), "1" | "true" | "yes" | "on"),
        Some(Value::Number(n)) => n.as_i64().unwrap_or(0) != 0,
        _ => false,
    }
}

fn f64ish(value: &Value, key: &str) -> Option<f64> {
    match value.get(key) {
        Some(Value::Number(n)) => n.as_f64().filter(|v| v.is_finite()),
        Some(Value::String(s)) => s.trim().parse::<f64>().ok().filter(|v| v.is_finite()),
        _ => None,
    }
}

fn clean_mac(mac: &str) -> String {
    mac.replace(':', "").replace('-', "").trim().to_ascii_uppercase()
}

fn replace_template(template: &str, router: &str, profile: &str, server: &str, plan: &str) -> String {
    template
        .replace("{router}", router)
        .replace("{profile}", profile)
        .replace("{server}", server)
        .replace("{plan}", plan)
}

fn parse_profile_name_speed(profile_name: &str) -> Option<BandwidthPair> {
    let re = Regex::new(r"(?i)(\d+(?:\.\d+)?)([kmg]?)\s*$").ok()?;
    let caps = re.captures(profile_name.trim())?;
    let raw = format!("{}{}", caps.get(1)?.as_str(), caps.get(2).map(|m| m.as_str()).unwrap_or(""));
    let mbps = convert_to_mbps(&raw);
    if mbps > 0.0 { Some(BandwidthPair { download_mbps: mbps, upload_mbps: mbps }) } else { None }
}

fn speed_from_text(raw: &str, parser: &str) -> Option<BandwidthPair> {
    if raw.trim().is_empty() { return None; }
    if parser == "rate_limit" {
        let p = parse_rate_limit(raw);
        if p.download_mbps > 0.0 && p.upload_mbps > 0.0 { Some(p) } else { None }
    } else if parser == "profile_name" {
        parse_profile_name_speed(raw)
    } else {
        parse_comment_bandwidth(raw)
    }
}

fn resolve_pppoe_speed(secret: &Value, active: &Value, profile: Option<&Value>, profile_name: &str, default_rate: &str) -> (BandwidthPair, String, String) {
    let profile = profile.unwrap_or(&Value::Null);
    let candidates = [
        (sval(secret, "comment"), "ppp_secret_comment", "comment"),
        (sval(active, "comment"), "ppp_active_comment", "comment"),
        (sval(profile, "comment"), "ppp_profile_comment", "comment"),
        (profile_name.to_string(), "ppp_profile_name", "profile_name"),
        (sval(profile, "rate-limit"), "ppp_profile_rate_limit", "rate_limit"),
        (default_rate.to_string(), "config_default_pppoe", "rate_limit"),
    ];
    for (raw, source, parser) in candidates {
        if let Some(pair) = speed_from_text(&raw, parser) {
            return (pair, source.to_string(), raw);
        }
    }
    (BandwidthPair { download_mbps: 10.0, upload_mbps: 10.0 }, "config_default_pppoe_fallback".to_string(), default_rate.to_string())
}

fn round3(value: f64) -> String {
    let rounded = (value * 1000.0).round() / 1000.0;
    if rounded.fract().abs() < f64::EPSILON {
        format!("{}", rounded as i64)
    } else {
        let mut s = format!("{rounded:.3}");
        while s.contains('.') && s.ends_with('0') { s.pop(); }
        if s.ends_with('.') { s.pop(); }
        s
    }
}

fn make_row(code: &str, device_name: &str, parent: &str, mac: &str, ipv4: &str, source: &str, pair: &BandwidthPair, min_rate_percentage: f64) -> ShapedDeviceRow {
    let mut fields = BTreeMap::new();
    for f in FIELDNAMES { fields.insert(f.to_string(), String::new()); }
    fields.insert("Circuit ID".to_string(), code.to_string());
    fields.insert("Circuit Name".to_string(), code.to_string());
    fields.insert("Device ID".to_string(), code.to_string());
    fields.insert("Device Name".to_string(), if device_name.trim().is_empty() { code.to_string() } else { device_name.to_string() });
    fields.insert("Parent Node".to_string(), parent.to_string());
    fields.insert("MAC".to_string(), mac.to_string());
    fields.insert("IPv4".to_string(), ipv4.to_string());
    fields.insert("IPv6".to_string(), String::new());
    fields.insert("Download Min Mbps".to_string(), round3(pair.download_mbps * min_rate_percentage));
    fields.insert("Upload Min Mbps".to_string(), round3(pair.upload_mbps * min_rate_percentage));
    fields.insert("Download Max Mbps".to_string(), round3(pair.download_mbps));
    fields.insert("Upload Max Mbps".to_string(), round3(pair.upload_mbps));
    fields.insert("Comment".to_string(), source.to_string());
    ShapedDeviceRow { fields }
}

fn row_json(row: &ShapedDeviceRow) -> Value { json!(row.fields) }

fn process_pppoe(payload: &Value, router: &Value, defaults: &Value, rows: &mut Vec<ShapedDeviceRow>, warnings: &mut Vec<Diagnostic>, meta: &mut Vec<Value>, min_rate_percentage: f64) -> usize {
    let Some(pppoe) = obj(payload, "pppoe") else { return 0; };
    let router_name = sval(router, "name");
    let router_name = if router_name.is_empty() { "Router".to_string() } else { router_name };
    let default_rate = sval(defaults, "default_pppoe_rate");
    let default_rate = if default_rate.is_empty() { "10M/10M".to_string() } else { default_rate };
    let router_pppoe = obj(router, "pppoe").unwrap_or(&Value::Null);
    let per_plan = boolish(router_pppoe, "per_plan_node");
    let plan_tpl = sval(router_pppoe, "plan_node_name");
    let plan_tpl = if plan_tpl.is_empty() { "{profile}-{router}".to_string() } else { plan_tpl };
    let flat_tpl = sval(router_pppoe, "flat_node_name");
    let flat_tpl = if flat_tpl.is_empty() { "PPP-{router}".to_string() } else { flat_tpl };

    let active_rows = arr(pppoe, "active");
    let secret_rows = arr(pppoe, "secrets");
    let profile_rows = arr(pppoe, "profiles");
    let mut active_by_name: HashMap<String, &Value> = HashMap::new();
    let mut secret_by_name: HashMap<String, &Value> = HashMap::new();
    let mut profile_by_name: HashMap<String, &Value> = HashMap::new();

    for a in active_rows { let name = sval(a, "name"); if !name.is_empty() { active_by_name.insert(name, a); } }
    for s in secret_rows {
        let name = sval(s, "name");
        if !name.is_empty() && !boolish(s, "disabled") && !boolish(s, "inactive") { secret_by_name.insert(name, s); }
    }
    for p in profile_rows { let name = sval(p, "name"); if !name.is_empty() { profile_by_name.insert(name, p); } }

    let mut count = 0;
    for (username, active) in active_by_name.iter() {
        let Some(secret) = secret_by_name.get(username) else {
            warnings.push(Diagnostic::warning(
                "pppoe_active_without_secret",
                Some(format!("pppoe.active.{username}")),
                format!("PPPoE active session {username} has no enabled matching secret; skipped in Rust shadow bundle."),
            ));
            continue;
        };
        let mac = sval(active, "caller-id");
        let mac = if mac.is_empty() { sval(secret, "caller-id") } else { mac };
        let ip = sval(active, "address");
        let profile_name = sval(secret, "profile");
        let profile_name = if profile_name.is_empty() { "default".to_string() } else { profile_name };
        let (pair, speed_source, raw_value) = resolve_pppoe_speed(secret, active, profile_by_name.get(&profile_name).copied(), &profile_name, &default_rate);
        let code = if !username.trim().is_empty() { username.to_string() } else { clean_mac(&mac) };
        if code.trim().is_empty() { continue; }
        let parent = if per_plan { replace_template(&plan_tpl, &router_name, &profile_name, "", "") } else { replace_template(&flat_tpl, &router_name, "", "", "") };
        rows.push(make_row(&code, username, &parent, &mac, &ip, "PPP", &pair, min_rate_percentage));
        meta.push(json!({"source":"PPP", "username": username, "router": router_name, "profile": profile_name, "speed_source": speed_source, "speed_raw_value": raw_value}));
        count += 1;
    }
    count
}

fn process_dhcp(payload: &Value, router: &Value, defaults: &Value, rows: &mut Vec<ShapedDeviceRow>, warnings: &mut Vec<Diagnostic>, meta: &mut Vec<Value>, min_rate_percentage: f64) -> usize {
    let Some(dhcp) = obj(payload, "dhcp") else { return 0; };
    let router_name = sval(router, "name");
    let router_name = if router_name.is_empty() { "Router".to_string() } else { router_name };
    let default_mbps = f64ish(defaults, "default_dhcp_per_client_mbps").unwrap_or(15.0);
    let router_dhcp = obj(router, "dhcp").unwrap_or(&Value::Null);
    let mut server_by_name: HashMap<String, &Value> = HashMap::new();
    if let Some(servers) = dhcp.get("servers").and_then(Value::as_array) {
        for server in servers { let name = sval(server, "name"); if !name.is_empty() { server_by_name.insert(name, server); } }
    }
    if let Some(servers) = router_dhcp.get("servers").and_then(Value::as_array) {
        for server in servers { let name = sval(server, "name"); if !name.is_empty() { server_by_name.entry(name).or_insert(server); } }
    }

    let mut count = 0;
    for lease in arr(dhcp, "leases") {
        if boolish(lease, "disabled") { continue; }
        let server_name = sval(lease, "server");
        let server = server_by_name.get(&server_name).copied().unwrap_or(&Value::Null);
        let hostname = sval(lease, "host-name");
        let mac = sval(lease, "mac-address");
        let ip = sval(lease, "address");
        let mac_clean = clean_mac(&mac);
        let code = if !hostname.trim().is_empty() { format!("DHCP-{hostname}") } else { format!("DHCP-{mac_clean}") };
        if code == "DHCP-" {
            warnings.push(Diagnostic::warning("dhcp_lease_missing_identity", Some("dhcp.leases".to_string()), "DHCP lease missing hostname and MAC; skipped."));
            continue;
        }
        let down = f64ish(server, "default_plan_down_mbps").or_else(|| f64ish(server, "download_limit_mbps")).unwrap_or(default_mbps);
        let up = f64ish(server, "default_plan_up_mbps").or_else(|| f64ish(server, "upload_limit_mbps")).unwrap_or(default_mbps);
        let tpl = sval(server, "node_name");
        let tpl = if tpl.is_empty() { "DHCP-{server}-{router}".to_string() } else { tpl };
        let parent = replace_template(&tpl, &router_name, "", &server_name, "");
        rows.push(make_row(&code, if hostname.is_empty() { &code } else { &hostname }, &parent, &mac, &ip, "DHCP", &BandwidthPair { download_mbps: down, upload_mbps: up }, min_rate_percentage));
        meta.push(json!({"source":"DHCP", "router": router_name, "server": server_name, "hostname": hostname, "speed_source":"dhcp_server_config"}));
        count += 1;
    }
    count
}

fn process_hotspot(payload: &Value, router: &Value, defaults: &Value, rows: &mut Vec<ShapedDeviceRow>, warnings: &mut Vec<Diagnostic>, meta: &mut Vec<Value>, min_rate_percentage: f64) -> usize {
    let Some(hs) = obj(payload, "hotspot") else { return 0; };
    let router_name = sval(router, "name");
    let router_name = if router_name.is_empty() { "Router".to_string() } else { router_name };
    let router_hs = obj(router, "hotspot").unwrap_or(&Value::Null);
    let include_mac = router_hs.get("include_mac").and_then(Value::as_bool).unwrap_or(true);
    let default_mbps = f64ish(defaults, "default_hotspot_per_client_mbps").unwrap_or(10.0);
    let down = f64ish(router_hs, "download_limit_mbps").unwrap_or(default_mbps);
    let up = f64ish(router_hs, "upload_limit_mbps").unwrap_or(default_mbps);
    let tpl = sval(router_hs, "node_name");
    let tpl = if tpl.is_empty() { "HS-{router}".to_string() } else { tpl };
    let parent = replace_template(&tpl, &router_name, "", "", "");

    let mut count = 0;
    for active in arr(hs, "active") {
        let username = sval(active, "user");
        let username = if username.is_empty() { sval(active, "name") } else { username };
        let mac = sval(active, "mac-address");
        let ip = sval(active, "address");
        let mac_clean = clean_mac(&mac);
        let code = if include_mac && !mac_clean.is_empty() { format!("HS-{mac_clean}") } else if !username.is_empty() { format!("HS-{username}") } else { String::new() };
        if code.is_empty() {
            warnings.push(Diagnostic::warning("hotspot_active_missing_identity", Some("hotspot.active".to_string()), "Hotspot active row missing username and MAC; skipped."));
            continue;
        }
        rows.push(make_row(&code, if username.is_empty() { &code } else { &username }, &parent, &mac, &ip, "HS", &BandwidthPair { download_mbps: down, upload_mbps: up }, min_rate_percentage));
        meta.push(json!({"source":"HS", "router": router_name, "username": username, "speed_source":"hotspot_config_speed"}));
        count += 1;
    }
    count
}

pub fn build_collector_circuit_bundle_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let router = obj(payload, "router").unwrap_or(&Value::Null);
    let defaults = obj(payload, "defaults").unwrap_or(&Value::Null);
    let min_rate_percentage = f64ish(defaults, "min_rate_percentage").or_else(|| f64ish(payload, "min_rate_percentage")).unwrap_or(0.5).clamp(0.0, 1.0);
    let mut rows: Vec<ShapedDeviceRow> = Vec::new();
    let errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let mut meta: Vec<Value> = Vec::new();

    let ppp_count = process_pppoe(payload, router, defaults, &mut rows, &mut warnings, &mut meta, min_rate_percentage);
    let dhcp_count = process_dhcp(payload, router, defaults, &mut rows, &mut warnings, &mut meta, min_rate_percentage);
    let hs_count = process_hotspot(payload, router, defaults, &mut rows, &mut warnings, &mut meta, min_rate_percentage);

    let mut duplicate_ips: HashMap<String, String> = HashMap::new();
    for row in &rows {
        let ip = row.get("IPv4").trim().to_string();
        let code = row.get("Circuit Name").to_string();
        if !ip.is_empty() {
            if let Some(prev) = duplicate_ips.get(&ip) {
                warnings.push(Diagnostic {
                    code: "duplicate_ip_shadow".to_string(),
                    severity: Severity::Warning,
                    path: Some("collector_bundle.rows".to_string()),
                    message: format!("Duplicate IPv4 {ip}: {prev} and {code}"),
                    value: Some(json!(ip)),
                    safe_for_cleanup: None,
                });
            } else { duplicate_ips.insert(ip, code); }
        }
    }

    if rows.is_empty() {
        warnings.push(Diagnostic::warning("collector_bundle_empty", Some("collector_bundle".to_string()), "Rust collector bundle produced zero circuit rows."));
    }

    let normalized_rows: Vec<Value> = rows.iter().map(row_json).collect();
    let result = json!({
        "mode": "shadow",
        "authoritative": false,
        "backend_transition": "collector_processing_shadow",
        "input_sources": {
            "pppoe_active": payload.get("pppoe").and_then(|v| v.get("active")).and_then(Value::as_array).map(|v| v.len()).unwrap_or(0),
            "dhcp_leases": payload.get("dhcp").and_then(|v| v.get("leases")).and_then(Value::as_array).map(|v| v.len()).unwrap_or(0),
            "hotspot_active": payload.get("hotspot").and_then(|v| v.get("active")).and_then(Value::as_array).map(|v| v.len()).unwrap_or(0)
        },
        "source_counts": {"PPP": ppp_count, "DHCP": dhcp_count, "HS": hs_count},
        "normalized_count": normalized_rows.len(),
        "warning_count": warnings.len(),
        "invalid_count": errors.len(),
        "normalized_rows": normalized_rows,
        "meta": meta,
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builds_pppoe_collector_bundle_shadow() {
        let payload = json!({
            "router": {"name":"RB5009", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
            "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
            "pppoe": {
                "active": [{"name":"user1", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
                "secrets": [{"name":"user1", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
                "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
            }
        });
        let (result, errors, warnings) = build_collector_circuit_bundle_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
        assert_eq!(result["normalized_count"], 1);
        assert_eq!(result["normalized_rows"][0]["Parent Node"], "15M-RB5009");
        assert_eq!(result["normalized_rows"][0]["Download Max Mbps"], "15");
        assert_eq!(result["normalized_rows"][0]["Comment"], "PPP");
    }

    #[test]
    fn warns_on_pppoe_active_without_secret() {
        let payload = json!({
            "router": {"name":"RB5009"},
            "defaults": {"default_pppoe_rate":"10M/10M"},
            "pppoe": {"active": [{"name":"ghost", "address":"10.0.0.3"}], "secrets": [], "profiles": []}
        });
        let (result, errors, warnings) = build_collector_circuit_bundle_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result["normalized_count"], 0);
        assert!(warnings.iter().any(|w| w.code == "pppoe_active_without_secret"));
    }

    #[test]
    fn builds_dhcp_and_hotspot_rows() {
        let payload = json!({
            "router": {
                "name":"RB5009",
                "dhcp":{"servers":[{"name":"LAN", "default_plan_down_mbps":20, "default_plan_up_mbps":10}]},
                "hotspot":{"download_limit_mbps":5, "upload_limit_mbps":5, "include_mac":true}
            },
            "defaults": {"min_rate_percentage":0.5},
            "dhcp": {"leases": [{"server":"LAN", "host-name":"phone", "mac-address":"11:22:33:44:55:66", "address":"192.168.1.10"}]},
            "hotspot": {"active": [{"user":"guest", "mac-address":"AA-BB-CC-00-11-22", "address":"192.168.22.10"}]}
        });
        let (result, errors, _warnings) = build_collector_circuit_bundle_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result["normalized_count"], 2);
        assert_eq!(result["source_counts"]["DHCP"], 1);
        assert_eq!(result["source_counts"]["HS"], 1);
    }
}
