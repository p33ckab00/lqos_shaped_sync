use crate::protocol::{Diagnostic, Severity};
use csv::{ReaderBuilder, WriterBuilder};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, HashMap};

pub const FIELDNAMES: [&str; 13] = [
    "Circuit ID",
    "Circuit Name",
    "Device ID",
    "Device Name",
    "Parent Node",
    "MAC",
    "IPv4",
    "IPv6",
    "Download Min Mbps",
    "Upload Min Mbps",
    "Download Max Mbps",
    "Upload Max Mbps",
    "Comment",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShapedDeviceRow {
    pub fields: BTreeMap<String, String>,
}

impl ShapedDeviceRow {
    pub fn get(&self, key: &str) -> &str {
        self.fields.get(key).map(|s| s.as_str()).unwrap_or("")
    }

    pub fn circuit_name(&self) -> &str {
        self.get("Circuit Name")
    }

    pub fn parent_node(&self) -> &str {
        self.get("Parent Node")
    }

    pub fn ipv4(&self) -> &str {
        self.get("IPv4").trim()
    }
}

pub fn parse_csv_text(text: &str) -> Result<Vec<ShapedDeviceRow>, csv::Error> {
    let mut reader = ReaderBuilder::new().flexible(true).from_reader(text.as_bytes());
    let headers = reader.headers()?.clone();
    let mut rows = Vec::new();
    for record in reader.records() {
        let record = record?;
        let mut fields = BTreeMap::new();
        for (idx, header) in headers.iter().enumerate() {
            fields.insert(header.to_string(), record.get(idx).unwrap_or("").trim().to_string());
        }
        for field in FIELDNAMES {
            fields.entry(field.to_string()).or_default();
        }
        if !fields.get("Circuit Name").map(|v| v.trim().is_empty()).unwrap_or(true) {
            rows.push(ShapedDeviceRow { fields });
        }
    }
    Ok(rows)
}

pub fn render_csv_text(rows: &[ShapedDeviceRow]) -> Result<String, csv::Error> {
    let mut output = Vec::new();
    {
        let mut writer = WriterBuilder::new().terminator(csv::Terminator::Any(b'\n')).from_writer(&mut output);
        writer.write_record(FIELDNAMES)?;
        let mut sorted = rows.to_vec();
        sorted.sort_by(|a, b| {
            (
                a.get("Parent Node"),
                a.get("Circuit Name"),
                a.get("Device Name"),
                a.get("IPv4"),
                a.get("MAC"),
            )
                .cmp(&(
                    b.get("Parent Node"),
                    b.get("Circuit Name"),
                    b.get("Device Name"),
                    b.get("IPv4"),
                    b.get("MAC"),
                ))
        });
        for row in sorted {
            let values: Vec<&str> = FIELDNAMES.iter().map(|field| row.get(field)).collect();
            writer.write_record(values)?;
        }
        writer.flush()?;
    }
    Ok(String::from_utf8_lossy(&output).to_string())
}

pub fn validate_rows(rows: &[ShapedDeviceRow], network_mode: &str, parent_nodes: Option<&std::collections::HashSet<String>>) -> (Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let mut seen_ips: HashMap<String, String> = HashMap::new();

    for (idx, row) in rows.iter().enumerate() {
        let code = if row.circuit_name().is_empty() {
            format!("row[{idx}]")
        } else {
            row.circuit_name().to_string()
        };

        if row.circuit_name().trim().is_empty() {
            errors.push(Diagnostic::error(
                "empty_circuit_name",
                Some(format!("rows[{idx}].Circuit Name")),
                "Empty Circuit Name",
            ));
        }

        if network_mode != "flat_no_parent" && row.parent_node().trim().is_empty() {
            errors.push(Diagnostic::error(
                "missing_parent_node",
                Some(format!("rows[{code}].Parent Node")),
                format!("Missing Parent Node for {code}"),
            ));
        }

        if let Some(nodes) = parent_nodes {
            let parent = row.parent_node().trim();
            if !parent.is_empty() && !nodes.contains(parent) {
                errors.push(Diagnostic::error(
                    "parent_node_not_found",
                    Some(format!("rows[{code}].Parent Node")),
                    format!("Parent Node '{parent}' for {code} does not exist in network.json"),
                )
                .with_value(json!(parent)));
            }
        }

        let ip = row.ipv4();
        if !ip.is_empty() {
            if let Some(previous) = seen_ips.get(ip) {
                warnings.push(Diagnostic {
                    code: "duplicate_ip".to_string(),
                    severity: Severity::Warning,
                    path: Some(format!("rows[{code}].IPv4")),
                    message: format!("Duplicate IP {ip}: {previous} and {code}"),
                    value: Some(json!(ip)),
                    safe_for_cleanup: None,
                });
            } else {
                seen_ips.insert(ip.to_string(), code.clone());
            }
        }

        for key in ["Download Min Mbps", "Upload Min Mbps", "Download Max Mbps", "Upload Max Mbps"] {
            let raw = row.get(key).trim();
            if raw.is_empty() {
                continue;
            }
            if raw.parse::<f64>().is_err() {
                errors.push(Diagnostic::error(
                    "invalid_bandwidth",
                    Some(format!("rows[{code}].{key}")),
                    format!("Invalid bandwidth {key} for {code}"),
                )
                .with_value(json!(raw)));
            }
        }
    }

    (errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_and_validates_csv() {
        let text = "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n1,c1,1,c1,PN,aa,10.0.0.2,,5,5,10,10,PPP\n2,c2,2,c2,PN,bb,10.0.0.2,,bad,5,10,10,DHCP\n";
        let rows = parse_csv_text(text).unwrap();
        assert_eq!(rows.len(), 2);
        let (errors, warnings) = validate_rows(&rows, "router_children", None);
        assert!(errors.iter().any(|e| e.code == "invalid_bandwidth"));
        assert!(warnings.iter().any(|w| w.code == "duplicate_ip"));
    }

    #[test]
    fn renders_sorted_csv() {
        let text = "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n2,b,2,b,Z,bb,10.0.0.3,,5,5,10,10,PPP\n1,a,1,a,A,aa,10.0.0.2,,5,5,10,10,PPP\n";
        let rows = parse_csv_text(text).unwrap();
        let rendered = render_csv_text(&rows).unwrap();
        assert!(rendered.find(",a,").unwrap() < rendered.find(",b,").unwrap());
    }
}
