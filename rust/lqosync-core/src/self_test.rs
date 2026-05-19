use crate::apply_manifest::build_apply_manifest_payload;
use crate::apply_transaction::execute_apply_transaction_payload;
use crate::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use crate::protocol::Diagnostic;
use crate::transaction_journal::{append_transaction_journal_payload, build_rollback_manifest_payload, build_transaction_journal_payload};
use crate::transaction_history::{build_rollback_from_journal_payload, read_transaction_journal_payload};
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
pub const OP_BUILD_TRANSACTION_JOURNAL: &str = "build-transaction-journal";
pub const OP_APPEND_TRANSACTION_JOURNAL: &str = "append-transaction-journal";
pub const OP_BUILD_ROLLBACK_MANIFEST: &str = "build-rollback-manifest";
pub const OP_READ_TRANSACTION_JOURNAL: &str = "read-transaction-journal";
pub const OP_BUILD_ROLLBACK_FROM_JOURNAL: &str = "build-rollback-from-journal";
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
        OP_BUILD_TRANSACTION_JOURNAL,
        OP_APPEND_TRANSACTION_JOURNAL,
        OP_BUILD_ROLLBACK_MANIFEST,
        OP_READ_TRANSACTION_JOURNAL,
        OP_BUILD_ROLLBACK_FROM_JOURNAL,
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
        "mode": "apply",
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

    let journal_payload = json!({
        "mode": "apply",
        "rust_apply_manifest": {"result": manifest.clone()},
        "rust_apply_transaction": {"result": tx.clone()},
        "rust_sync_plan": {"result": {"verdict": "no_changes"}},
        "paths": {"transaction_journal": "/tmp/transaction_journal.jsonl"}
    });
    let (journal, journal_errors, _journal_warnings) = build_transaction_journal_payload(&journal_payload);
    let journal_ok = journal_errors.is_empty() && journal.get("append_executed").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("transaction_journal_preview", journal_ok, json!({"journal_id": journal.get("journal_id"), "append_executed": journal.get("append_executed")})));
    if !journal_ok {
        errors.push(Diagnostic::error("self_test_transaction_journal_failed", Some("build-transaction-journal".to_string()), "Self-test transaction journal preview should be non-mutating and valid."));
    }

    let mut append_payload = journal_payload.clone();
    if let Some(obj) = append_payload.as_object_mut() {
        obj.insert("append".to_string(), json!(false));
        obj.insert("allow_journal_write".to_string(), json!(false));
    }
    let (journal_append, journal_append_errors, _journal_append_warnings) = append_transaction_journal_payload(&append_payload);
    let journal_append_ok = journal_append_errors.is_empty() && journal_append.get("append_executed").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("transaction_journal_append_rehearsal", journal_append_ok, json!({"status": journal_append.get("status"), "append_executed": journal_append.get("append_executed")})));
    if !journal_append_ok {
        errors.push(Diagnostic::error("self_test_transaction_journal_append_failed", Some("append-transaction-journal".to_string()), "Self-test transaction journal append rehearsal should not write."));
    }

    let (rollback, rollback_errors, _rollback_warnings) = build_rollback_manifest_payload(&journal_payload);
    let rollback_ok = rollback_errors.is_empty() && rollback.get("execute_supported").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("rollback_manifest_preview", rollback_ok, json!({"status": rollback.get("status"), "execute_supported": rollback.get("execute_supported")})));
    if !rollback_ok {
        errors.push(Diagnostic::error("self_test_rollback_manifest_failed", Some("build-rollback-manifest".to_string()), "Self-test rollback manifest should be preview-only and valid."));
    }

    let journal_event = journal.get("event").cloned().unwrap_or_else(|| json!({}));
    let temp_journal_path = std::env::temp_dir().join(format!("lqosync-core-self-test-journal-{}.jsonl", std::process::id()));
    let _ = std::fs::write(&temp_journal_path, format!("{}\n", serde_json::to_string(&journal_event).unwrap_or_default()));
    let temp_journal = temp_journal_path.to_string_lossy().to_string();
    let (history, history_errors, _history_warnings) = read_transaction_journal_payload(&json!({"path": temp_journal, "limit": 1}));
    let history_ok = history_errors.is_empty() && history.get("returned_count").and_then(Value::as_u64).unwrap_or(0) >= 1;
    checks.push(check("transaction_journal_reader", history_ok, json!({"returned_count": history.get("returned_count"), "status": history.get("status")})));
    if !history_ok {
        errors.push(Diagnostic::error("self_test_transaction_journal_reader_failed", Some("read-transaction-journal".to_string()), "Self-test transaction journal reader should read a temporary JSONL entry."));
    }

    let journal_id = journal_event.get("journal_id").and_then(Value::as_str).unwrap_or("");
    let (rollback_from_journal, rollback_from_journal_errors, _rollback_from_journal_warnings) = build_rollback_from_journal_payload(&json!({"path": temp_journal_path.to_string_lossy(), "journal_id": journal_id}));
    let rollback_from_journal_ok = rollback_from_journal_errors.is_empty() && rollback_from_journal.get("execute_supported").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("rollback_from_journal_preview", rollback_from_journal_ok, json!({"status": rollback_from_journal.get("status"), "source": rollback_from_journal.get("source")})));
    if !rollback_from_journal_ok {
        errors.push(Diagnostic::error("self_test_rollback_from_journal_failed", Some("build-rollback-from-journal".to_string()), "Self-test rollback-from-journal should build a preview from a temporary JSONL entry."));
    }
    let _ = std::fs::remove_file(temp_journal_path);

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
        "check_count": checks.len(),
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
        assert!(ops.contains(&OP_BUILD_TRANSACTION_JOURNAL));
        assert!(ops.contains(&OP_APPEND_TRANSACTION_JOURNAL));
        assert!(ops.contains(&OP_BUILD_ROLLBACK_MANIFEST));
        assert!(ops.contains(&OP_READ_TRANSACTION_JOURNAL));
        assert!(ops.contains(&OP_BUILD_ROLLBACK_FROM_JOURNAL));
        assert!(ops.contains(&OP_SELF_TEST));
    }
}
