use crate::apply_manifest::build_apply_manifest_payload;
use crate::apply_transaction::execute_apply_transaction_payload;
use crate::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use crate::protocol::Diagnostic;
use serde_json::{json, Value};

pub const OP_HEALTH: &str = "health";
pub const OP_PARSE_BANDWIDTH: &str = "parse-bandwidth";
pub const OP_VALIDATE_CONFIG: &str = "validate-config";
pub const OP_VALIDATE_SHAPED_DEVICES: &str = "validate-shaped-devices";
pub const OP_VALIDATE_NETWORK: &str = "validate-network";
pub const OP_VALIDATE_FILES: &str = "validate-files";
pub const OP_VALIDATE_COLLECTOR_OUTPUT: &str = "validate-collector-output";
pub const OP_DIFF_SHAPED_DEVICES: &str = "diff-shaped-devices";
pub const OP_DIFF_NETWORK: &str = "diff-network";
pub const OP_DIFF_FILES: &str = "diff-files";
pub const OP_VALIDATE_JSON_STATE: &str = "validate-json-state";
pub const OP_WRITE_JSON_STATE: &str = "write-json-state";
pub const OP_WRITE_TEXT_FILE: &str = "write-text-file";
pub const OP_APPEND_AUDIT_JSONL: &str = "append-audit-jsonl";
pub const OP_EVALUATE_POLICY: &str = "evaluate-policy";
pub const OP_NORMALIZE_CIRCUITS: &str = "normalize-circuits";
pub const OP_EVALUATE_SYNC_PLAN: &str = "evaluate-sync-plan";
pub const OP_BUILD_APPLY_MANIFEST: &str = "build-apply-manifest";
pub const OP_EXECUTE_APPLY_TRANSACTION: &str = "execute-apply-transaction";
pub const OP_SELF_TEST: &str = "self-test";

pub fn advertised_operations() -> &'static [&'static str] {
    &[
        OP_HEALTH,
        OP_PARSE_BANDWIDTH,
        OP_VALIDATE_CONFIG,
        OP_VALIDATE_SHAPED_DEVICES,
        OP_VALIDATE_NETWORK,
        OP_VALIDATE_FILES,
        OP_VALIDATE_COLLECTOR_OUTPUT,
        OP_DIFF_SHAPED_DEVICES,
        OP_DIFF_NETWORK,
        OP_DIFF_FILES,
        OP_VALIDATE_JSON_STATE,
        OP_WRITE_JSON_STATE,
        OP_WRITE_TEXT_FILE,
        OP_APPEND_AUDIT_JSONL,
        OP_EVALUATE_POLICY,
        OP_NORMALIZE_CIRCUITS,
        OP_EVALUATE_SYNC_PLAN,
        OP_BUILD_APPLY_MANIFEST,
        OP_EXECUTE_APPLY_TRANSACTION,
        OP_SELF_TEST,
    ]
}

fn check(name: &str, ok: bool, details: Value) -> Value {
    json!({"name": name, "ok": ok, "details": details})
}

pub fn self_test_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let warnings: Vec<Diagnostic> = Vec::new();
    let mut checks: Vec<Value> = Vec::new();

    let operations = advertised_operations();
    let unique_count = operations.iter().collect::<std::collections::BTreeSet<_>>().len();
    let operations_unique = unique_count == operations.len();
    checks.push(check(
        "advertised_operations_unique",
        operations_unique,
        json!({"operation_count": operations.len(), "unique_count": unique_count}),
    ));
    if !operations_unique {
        errors.push(Diagnostic::error(
            "duplicate_advertised_operations",
            Some("operations".to_string()),
            "One or more Rust core operations are advertised more than once.",
        ));
    }

    let has_transaction = operations.contains(&OP_EXECUTE_APPLY_TRANSACTION);
    checks.push(check(
        "execute_apply_transaction_advertised",
        has_transaction,
        json!({"operation": OP_EXECUTE_APPLY_TRANSACTION}),
    ));
    if !has_transaction {
        errors.push(Diagnostic::error(
            "transaction_operation_not_advertised",
            Some("operations".to_string()),
            "execute-apply-transaction is not advertised by the Rust core.",
        ));
    }

    let unit_mbps = convert_to_mbps("1G");
    let unit_ok = (unit_mbps - 1000.0).abs() < f64::EPSILON;
    checks.push(check("bandwidth_unit_parser", unit_ok, json!({"input":"1G", "mbps": unit_mbps})));
    if !unit_ok {
        errors.push(Diagnostic::error("self_test_bandwidth_unit_failed", Some("bandwidth".to_string()), "1G should parse as 1000 Mbps."));
    }

    let rate = parse_rate_limit("10M/5M");
    let rate_ok = (rate.download_mbps - 10.0).abs() < f64::EPSILON && (rate.upload_mbps - 5.0).abs() < f64::EPSILON;
    checks.push(check("bandwidth_rate_limit_parser", rate_ok, json!({"download_mbps": rate.download_mbps, "upload_mbps": rate.upload_mbps})));
    if !rate_ok {
        errors.push(Diagnostic::error("self_test_rate_limit_failed", Some("bandwidth".to_string()), "10M/5M should parse as 10/5 Mbps."));
    }

    let comment_ok = parse_comment_bandwidth("PLAN|15M/15M")
        .map(|v| (v.download_mbps - 15.0).abs() < f64::EPSILON && (v.upload_mbps - 15.0).abs() < f64::EPSILON)
        .unwrap_or(false);
    checks.push(check("bandwidth_comment_parser", comment_ok, json!({"input":"PLAN|15M/15M"})));
    if !comment_ok {
        errors.push(Diagnostic::error("self_test_comment_bandwidth_failed", Some("bandwidth".to_string()), "PLAN|15M/15M should parse as 15/15 Mbps."));
    }

    let manifest_payload = json!({
        "mode": "dry_run",
        "config": {"app": {"auto_apply": true, "backup_before_apply": false}, "libreqos": {"retry_if_last_apply_failed": true}},
        "paths": {"shaped_devices_csv": "/tmp/ShapedDevices.csv", "network_json": "/tmp/network.json", "runtime_state": "/tmp/runtime_state.json", "backup_dir": "/tmp/backups"},
        "state": {},
        "current_csv_text": "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n",
        "proposed_csv_text": "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n",
        "current_network_text": "{}",
        "proposed_network_text": "{}",
        "files_changed": false,
        "csv_changed": false,
        "network_changed": false,
        "policy_decision": {"write_allowed": true, "apply_allowed": true},
        "rust_sync_plan": {"result": {"verdict": "no_changes"}},
        "rust_authority_gate": {"should_block": false}
    });
    let (manifest, manifest_errors, manifest_warnings) = build_apply_manifest_payload(&manifest_payload);
    let manifest_ok = manifest_errors.is_empty() && manifest.get("status").and_then(Value::as_str).unwrap_or("") == "no_changes";
    checks.push(check("apply_manifest_no_changes", manifest_ok, json!({"status": manifest.get("status"), "warning_count": manifest_warnings.len()})));
    if !manifest_ok {
        errors.push(Diagnostic::error("self_test_apply_manifest_failed", Some("build-apply-manifest".to_string()), "Self-test no-changes apply manifest did not produce expected status."));
    }

    let mut tx_payload = manifest_payload.clone();
    if let Some(obj) = tx_payload.as_object_mut() {
        obj.insert("execute".to_string(), json!(false));
        obj.insert("allow_file_writes".to_string(), json!(false));
        obj.insert("allow_libreqos_apply".to_string(), json!(false));
    }
    let (tx, tx_errors, _tx_warnings) = execute_apply_transaction_payload(&tx_payload);
    let tx_ok = tx_errors.is_empty() && tx.get("executed").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("apply_transaction_rehearsal", tx_ok, json!({"status": tx.get("status"), "executed": tx.get("executed")})));
    if !tx_ok {
        errors.push(Diagnostic::error("self_test_apply_transaction_failed", Some("execute-apply-transaction".to_string()), "Self-test transaction rehearsal should not execute writes."));
    }

    let strict = payload.get("strict").and_then(Value::as_bool).unwrap_or(false);
    let status = if errors.is_empty() { "ok" } else { "failed" };
    let failed_check_count = checks.iter().filter(|c| !c.get("ok").and_then(Value::as_bool).unwrap_or(false)).count();
    let result = json!({
        "status": status,
        "strict": strict,
        "protocol_version": crate::protocol::PROTOCOL_VERSION,
        "operation_count": operations.len(),
        "operations": operations,
        "checks": checks,
        "check_count": operations.len().saturating_sub(operations.len()) + 6,
        "failed_check_count": failed_check_count,
        "purpose": "Verify that the installed Rust core binary/daemon advertises and can internally exercise critical parser, manifest, and transaction paths."
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn self_test_passes() {
        let (_result, errors, _warnings) = self_test_payload(&json!({}));
        assert!(errors.is_empty(), "self-test errors: {errors:?}");
    }

    #[test]
    fn operations_include_transaction_and_self_test() {
        let ops = advertised_operations();
        assert!(ops.contains(&OP_EXECUTE_APPLY_TRANSACTION));
        assert!(ops.contains(&OP_SELF_TEST));
    }
}
