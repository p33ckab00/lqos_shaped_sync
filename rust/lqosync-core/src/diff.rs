use crate::network::{collect_node_names, parse_network_text};
use crate::protocol::Diagnostic;
use crate::shaped_devices::{parse_csv_text, ShapedDeviceRow};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

fn rows_by_circuit(rows: Vec<ShapedDeviceRow>) -> BTreeMap<String, ShapedDeviceRow> {
    let mut out = BTreeMap::new();
    for row in rows {
        let key = row.circuit_name().trim().to_string();
        if !key.is_empty() {
            out.insert(key, row);
        }
    }
    out
}

pub fn diff_shaped_devices_text(current_text: &str, proposed_text: &str) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors = Vec::new();
    let warnings = Vec::new();

    let current = match parse_csv_text(current_text) {
        Ok(rows) => rows_by_circuit(rows),
        Err(e) => {
            errors.push(Diagnostic::error(
                "invalid_current_shaped_devices_csv",
                Some("current_csv".to_string()),
                format!("Current ShapedDevices.csv parse failed: {e}"),
            ));
            BTreeMap::new()
        }
    };
    let proposed = match parse_csv_text(proposed_text) {
        Ok(rows) => rows_by_circuit(rows),
        Err(e) => {
            errors.push(Diagnostic::error(
                "invalid_proposed_shaped_devices_csv",
                Some("proposed_csv".to_string()),
                format!("Proposed ShapedDevices.csv parse failed: {e}"),
            ));
            BTreeMap::new()
        }
    };

    let current_keys: BTreeSet<String> = current.keys().cloned().collect();
    let proposed_keys: BTreeSet<String> = proposed.keys().cloned().collect();
    let added: Vec<String> = proposed_keys.difference(&current_keys).cloned().collect();
    let removed: Vec<String> = current_keys.difference(&proposed_keys).cloned().collect();

    let mut updated = Vec::new();
    for key in current_keys.intersection(&proposed_keys) {
        let old = current.get(key).expect("intersection key exists in current");
        let new = proposed.get(key).expect("intersection key exists in proposed");
        if old.fields != new.fields {
            let mut changed_fields = Vec::new();
            let field_keys: BTreeSet<String> = old.fields.keys().chain(new.fields.keys()).cloned().collect();
            for field in field_keys {
                if old.fields.get(&field) != new.fields.get(&field) {
                    changed_fields.push(field);
                }
            }
            updated.push(json!({
                "circuit_name": key,
                "changed_fields": changed_fields,
            }));
        }
    }

    let result = json!({
        "current_count": current.len(),
        "proposed_count": proposed.len(),
        "added_count": added.len(),
        "removed_count": removed.len(),
        "updated_count": updated.len(),
        "changed": !added.is_empty() || !removed.is_empty() || !updated.is_empty(),
        "added": added,
        "removed": removed,
        "updated": updated,
    });

    (result, errors, warnings)
}

pub fn diff_network_text(current_text: &str, proposed_text: &str) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors = Vec::new();
    let warnings = Vec::new();

    let current = match parse_network_text(current_text) {
        Ok(v) => v,
        Err(e) => {
            errors.push(Diagnostic::error(
                "invalid_current_network_json",
                Some("current_network".to_string()),
                format!("Current network.json parse failed: {e}"),
            ));
            json!({})
        }
    };
    let proposed = match parse_network_text(proposed_text) {
        Ok(v) => v,
        Err(e) => {
            errors.push(Diagnostic::error(
                "invalid_proposed_network_json",
                Some("proposed_network".to_string()),
                format!("Proposed network.json parse failed: {e}"),
            ));
            json!({})
        }
    };

    let current_nodes: BTreeSet<String> = collect_node_names(&current).into_iter().collect();
    let proposed_nodes: BTreeSet<String> = collect_node_names(&proposed).into_iter().collect();
    let added_nodes: Vec<String> = proposed_nodes.difference(&current_nodes).cloned().collect();
    let removed_nodes: Vec<String> = current_nodes.difference(&proposed_nodes).cloned().collect();
    let changed = current != proposed;

    let result = json!({
        "current_node_count": current_nodes.len(),
        "proposed_node_count": proposed_nodes.len(),
        "added_node_count": added_nodes.len(),
        "removed_node_count": removed_nodes.len(),
        "changed": changed,
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
    });

    (result, errors, warnings)
}

pub fn diff_files_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let current_csv = payload.get("current_csv_text").and_then(Value::as_str).unwrap_or("");
    let proposed_csv = payload.get("proposed_csv_text").and_then(Value::as_str).unwrap_or("");
    let current_network = payload.get("current_network_text").and_then(Value::as_str).unwrap_or("{}");
    let proposed_network = payload.get("proposed_network_text").and_then(Value::as_str).unwrap_or("{}");

    let (csv, mut csv_errors, mut csv_warnings) = diff_shaped_devices_text(current_csv, proposed_csv);
    let (network, mut net_errors, mut net_warnings) = diff_network_text(current_network, proposed_network);

    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    errors.append(&mut csv_errors);
    errors.append(&mut net_errors);
    warnings.append(&mut csv_warnings);
    warnings.append(&mut net_warnings);

    let result = json!({
        "csv": csv,
        "network": network,
        "changed": csv.get("changed").and_then(Value::as_bool).unwrap_or(false)
            || network.get("changed").and_then(Value::as_bool).unwrap_or(false),
        "write_allowed": errors.is_empty(),
        "apply_allowed": errors.is_empty(),
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_added_removed_and_updated_rows() {
        let current = "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n1,a,1,a,PN,aa,10.0.0.2,,5,5,10,10,PPP\n2,b,2,b,PN,bb,10.0.0.3,,5,5,10,10,PPP\n";
        let proposed = "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n1,a,1,a,PN,aa,10.0.0.2,,5,5,20,20,PPP\n3,c,3,c,PN,cc,10.0.0.4,,5,5,10,10,DHCP\n";
        let (result, errors, _warnings) = diff_shaped_devices_text(current, proposed);
        assert!(errors.is_empty());
        assert_eq!(result["added_count"], 1);
        assert_eq!(result["removed_count"], 1);
        assert_eq!(result["updated_count"], 1);
    }
}
