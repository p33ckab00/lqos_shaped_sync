use crate::protocol::{Diagnostic, Severity};
use crate::shaped_devices::{ShapedDeviceRow, FIELDNAMES};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};

fn text<'a>(value: &'a Value, keys: &[&str]) -> String {
    for key in keys {
        if let Some(v) = value.get(*key) {
            if let Some(s) = v.as_str() {
                let trimmed = s.trim();
                if !trimmed.is_empty() {
                    return trimmed.to_string();
                }
            } else if v.is_number() || v.is_boolean() {
                return v.to_string();
            }
        }
    }
    String::new()
}

fn number(value: &Value, keys: &[&str]) -> Option<f64> {
    for key in keys {
        if let Some(v) = value.get(*key) {
            if let Some(n) = v.as_f64() {
                if n.is_finite() {
                    return Some(n);
                }
            }
            if let Some(s) = v.as_str() {
                if let Ok(n) = s.trim().parse::<f64>() {
                    if n.is_finite() {
                        return Some(n);
                    }
                }
            }
        }
    }
    None
}

fn source_comment(source: &str) -> String {
    match source.to_ascii_lowercase().as_str() {
        "ppp" | "pppoe" => "PPP".to_string(),
        "dhcp" => "DHCP".to_string(),
        "hs" | "hotspot" => "HS".to_string(),
        "static" => "static".to_string(),
        other if !other.is_empty() => other.to_uppercase(),
        _ => "UNKNOWN".to_string(),
    }
}

fn round3(value: f64) -> String {
    let rounded = (value * 1000.0).round() / 1000.0;
    if (rounded.fract()).abs() < f64::EPSILON {
        format!("{}", rounded as i64)
    } else {
        let mut s = format!("{rounded:.3}");
        while s.contains('.') && s.ends_with('0') {
            s.pop();
        }
        if s.ends_with('.') {
            s.pop();
        }
        s
    }
}

fn record_to_row(record: &Value, idx: usize, default_source: &str, default_router: &str, min_rate_percentage: f64) -> (Option<ShapedDeviceRow>, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let source = text(record, &["source", "source_type", "comment"]).trim().to_string();
    let source = if source.is_empty() { default_source.to_string() } else { source };
    let router = text(record, &["router", "router_name"]);
    let router = if router.is_empty() { default_router.to_string() } else { router };
    let code = text(record, &["code", "circuit_id", "Circuit ID", "Circuit Name", "circuit_name"]);
    let circuit_name = text(record, &["circuit_name", "Circuit Name", "code", "circuit_id"]);
    let device_name = text(record, &["device_name", "Device Name", "name", "username", "hostname"]);
    let parent_node = text(record, &["parent_node", "Parent Node"]);
    let mac = text(record, &["mac", "MAC", "caller-id", "caller_id"]);
    let ipv4 = text(record, &["ipv4", "IPv4", "address", "ip"]);
    let ipv6 = text(record, &["ipv6", "IPv6"]);

    let label = if !circuit_name.is_empty() { circuit_name.clone() } else { format!("record[{idx}]") };

    if circuit_name.is_empty() {
        errors.push(Diagnostic::error(
            "missing_circuit_name",
            Some(format!("records[{idx}].circuit_name")),
            "Circuit record is missing circuit_name/code",
        ));
    }
    if parent_node.is_empty() {
        warnings.push(Diagnostic::warning(
            "missing_parent_node",
            Some(format!("records[{idx}].parent_node")),
            format!("Circuit {label} has no Parent Node"),
        ));
    }

    let max_down = number(record, &["download_max_mbps", "Download Max Mbps", "download_mbps", "base_rx", "rx_mbps"]);
    let max_up = number(record, &["upload_max_mbps", "Upload Max Mbps", "upload_mbps", "base_tx", "tx_mbps"]);
    let (max_down, max_up) = match (max_down, max_up) {
        (Some(d), Some(u)) if d > 0.0 && u > 0.0 => (d, u),
        _ => {
            errors.push(Diagnostic::error(
                "invalid_circuit_speed",
                Some(format!("records[{idx}].speed")),
                format!("Circuit {label} has invalid or missing download/upload Mbps"),
            ));
            return (None, errors, warnings);
        }
    };

    let min_down = number(record, &["download_min_mbps", "Download Min Mbps"]).unwrap_or(max_down * min_rate_percentage);
    let min_up = number(record, &["upload_min_mbps", "Upload Min Mbps"]).unwrap_or(max_up * min_rate_percentage);

    if min_down < 0.0 || min_up < 0.0 || min_down > max_down || min_up > max_up {
        warnings.push(Diagnostic {
            code: "unusual_min_max_ratio".to_string(),
            severity: Severity::Warning,
            path: Some(format!("records[{idx}].min_max")),
            message: format!("Circuit {label} has unusual min/max bandwidth ratio"),
            value: Some(json!({"download_min": min_down, "download_max": max_down, "upload_min": min_up, "upload_max": max_up})),
            safe_for_cleanup: None,
        });
    }

    let mut fields = BTreeMap::new();
    for field in FIELDNAMES {
        fields.insert(field.to_string(), String::new());
    }
    let circuit_id = if code.is_empty() { circuit_name.clone() } else { code };
    fields.insert("Circuit ID".to_string(), circuit_id.clone());
    fields.insert("Circuit Name".to_string(), circuit_name.clone());
    fields.insert("Device ID".to_string(), circuit_id);
    fields.insert("Device Name".to_string(), if device_name.is_empty() { circuit_name } else { device_name });
    fields.insert("Parent Node".to_string(), parent_node);
    fields.insert("MAC".to_string(), mac);
    fields.insert("IPv4".to_string(), ipv4);
    fields.insert("IPv6".to_string(), ipv6);
    fields.insert("Download Min Mbps".to_string(), round3(min_down));
    fields.insert("Upload Min Mbps".to_string(), round3(min_up));
    fields.insert("Download Max Mbps".to_string(), round3(max_down));
    fields.insert("Upload Max Mbps".to_string(), round3(max_up));
    fields.insert("Comment".to_string(), source_comment(&source));
    if !router.is_empty() {
        // Router is not a LibreQoS CSV field; it is preserved in diagnostics/result summaries only.
    }
    (Some(ShapedDeviceRow { fields }), errors, warnings)
}

pub fn normalize_circuits_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let source = payload.get("source").and_then(Value::as_str).unwrap_or("mixed");
    let router = payload.get("router").and_then(Value::as_str).unwrap_or("mixed");
    let min_rate_percentage = payload
        .get("min_rate_percentage")
        .and_then(Value::as_f64)
        .filter(|v| v.is_finite() && *v >= 0.0 && *v <= 1.0)
        .unwrap_or(0.5);
    let records = payload.get("records").and_then(Value::as_array).cloned().unwrap_or_default();

    let mut rows = Vec::new();
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let mut duplicate_ips: HashMap<String, String> = HashMap::new();
    let mut source_counts: HashMap<String, usize> = HashMap::new();

    for (idx, record) in records.iter().enumerate() {
        let (row_opt, mut rec_errors, mut rec_warnings) = record_to_row(record, idx, source, router, min_rate_percentage);
        errors.append(&mut rec_errors);
        warnings.append(&mut rec_warnings);
        if let Some(row) = row_opt {
            let ip = row.get("IPv4").trim().to_string();
            let code = row.get("Circuit Name").to_string();
            if !ip.is_empty() {
                if let Some(prev) = duplicate_ips.get(&ip) {
                    warnings.push(Diagnostic {
                        code: "duplicate_ip".to_string(),
                        severity: Severity::Warning,
                        path: Some(format!("records[{idx}].ipv4")),
                        message: format!("Duplicate IPv4 {ip}: {prev} and {code}"),
                        value: Some(json!(ip)),
                        safe_for_cleanup: None,
                    });
                } else {
                    duplicate_ips.insert(ip, code);
                }
            }
            let comment = row.get("Comment").to_string();
            *source_counts.entry(comment).or_insert(0) += 1;
            rows.push(row);
        }
    }

    let normalized_rows: Vec<Value> = rows.iter().map(|row| json!(row.fields)).collect();
    let result = json!({
        "mode": "shadow",
        "authoritative": false,
        "source": source,
        "router": router,
        "input_count": records.len(),
        "normalized_count": normalized_rows.len(),
        "invalid_count": errors.len(),
        "warning_count": warnings.len(),
        "source_counts": source_counts,
        "normalized_rows": normalized_rows,
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_basic_circuit_record() {
        let payload = json!({
            "source": "pppoe",
            "router": "RB5009",
            "min_rate_percentage": 0.5,
            "records": [{
                "code": "user1-aa",
                "circuit_name": "user1-aa",
                "device_name": "user1",
                "parent_node": "15M-RB5009",
                "mac": "AA:BB:CC:DD:EE:FF",
                "ipv4": "10.0.0.2",
                "download_mbps": 15,
                "upload_mbps": 15
            }]
        });
        let (result, errors, warnings) = normalize_circuits_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
        assert_eq!(result["normalized_count"], 1);
        assert_eq!(result["normalized_rows"][0]["Download Min Mbps"], "7.5");
        assert_eq!(result["normalized_rows"][0]["Comment"], "PPP");
    }

    #[test]
    fn rejects_missing_speed() {
        let payload = json!({"records": [{"code": "bad", "circuit_name": "bad"}]});
        let (_result, errors, warnings) = normalize_circuits_payload(&payload);
        assert!(!errors.is_empty());
        assert!(!warnings.is_empty());
    }
}
