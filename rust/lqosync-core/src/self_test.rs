use crate::apply_manifest::build_apply_manifest_payload;
use crate::apply_transaction::execute_apply_transaction_payload;
use crate::authority_readiness::evaluate_authority_readiness_payload;
use crate::authority_pilot::{build_authority_pilot_plan_payload, evaluate_full_rust_readiness_payload};
use crate::bandwidth::{convert_to_mbps, parse_comment_bandwidth, parse_rate_limit};
use crate::collector_bundle::build_collector_circuit_bundle_payload;
use crate::collector_parity::compare_collector_bundle_parity_payload;
use crate::protocol::Diagnostic;
use crate::rollback_executor::execute_rollback_payload;
use crate::routeros_plan::build_routeros_collector_plan_payload;
use crate::routeros_results::validate_routeros_read_results_payload;
use crate::routeros_transport::build_routeros_transport_session_payload;
use crate::routeros_live_pilot::build_routeros_live_read_pilot_payload;
use crate::routeros_read_pilot::run_routeros_read_pilot_payload;
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
pub const OP_BUILD_ROUTEROS_COLLECTOR_PLAN: &str = "build-routeros-collector-plan";
pub const OP_VALIDATE_ROUTEROS_READ_RESULTS: &str = "validate-routeros-read-results";
pub const OP_BUILD_ROUTEROS_TRANSPORT_SESSION: &str = "build-routeros-transport-session";
pub const OP_BUILD_ROUTEROS_LIVE_READ_PILOT: &str = "build-routeros-live-read-pilot";
pub const OP_RUN_ROUTEROS_READ_PILOT: &str = "run-routeros-read-pilot";
pub const OP_BUILD_COLLECTOR_CIRCUIT_BUNDLE: &str = "build-collector-circuit-bundle";
pub const OP_COMPARE_COLLECTOR_BUNDLE_PARITY: &str = "compare-collector-bundle-parity";
pub const OP_EVALUATE_SYNC_PLAN: &str = "evaluate-sync-plan";
pub const OP_BUILD_APPLY_MANIFEST: &str = "build-apply-manifest";
pub const OP_EXECUTE_APPLY_TRANSACTION: &str = "execute-apply-transaction";
pub const OP_BUILD_TRANSACTION_JOURNAL: &str = "build-transaction-journal";
pub const OP_APPEND_TRANSACTION_JOURNAL: &str = "append-transaction-journal";
pub const OP_BUILD_ROLLBACK_MANIFEST: &str = "build-rollback-manifest";
pub const OP_READ_TRANSACTION_JOURNAL: &str = "read-transaction-journal";
pub const OP_BUILD_ROLLBACK_FROM_JOURNAL: &str = "build-rollback-from-journal";
pub const OP_EXECUTE_ROLLBACK: &str = "execute-rollback";
pub const OP_EVALUATE_AUTHORITY_READINESS: &str = "evaluate-authority-readiness";
pub const OP_EVALUATE_FULL_RUST_READINESS: &str = "evaluate-full-rust-readiness";
pub const OP_BUILD_AUTHORITY_PILOT_PLAN: &str = "build-authority-pilot-plan";
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
        OP_BUILD_ROUTEROS_COLLECTOR_PLAN,
        OP_VALIDATE_ROUTEROS_READ_RESULTS,
        OP_BUILD_ROUTEROS_TRANSPORT_SESSION,
        OP_BUILD_ROUTEROS_LIVE_READ_PILOT,
        OP_RUN_ROUTEROS_READ_PILOT,
        OP_BUILD_COLLECTOR_CIRCUIT_BUNDLE,
        OP_COMPARE_COLLECTOR_BUNDLE_PARITY,
        OP_EVALUATE_SYNC_PLAN,
        OP_BUILD_APPLY_MANIFEST,
        OP_EXECUTE_APPLY_TRANSACTION,
        OP_BUILD_TRANSACTION_JOURNAL,
        OP_APPEND_TRANSACTION_JOURNAL,
        OP_BUILD_ROLLBACK_MANIFEST,
        OP_READ_TRANSACTION_JOURNAL,
        OP_BUILD_ROLLBACK_FROM_JOURNAL,
        OP_EXECUTE_ROLLBACK,
        OP_EVALUATE_AUTHORITY_READINESS,
        OP_EVALUATE_FULL_RUST_READINESS,
        OP_BUILD_AUTHORITY_PILOT_PLAN,
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


    let routeros_plan_payload = json!({
        "config": {
            "collector": {"dhcp": {"read_server_metadata": true}},
            "routers": [{
                "name":"RB5009",
                "enabled": true,
                "pppoe":{"enabled":true},
                "dhcp":{"enabled":true, "servers":[{"name":"LAN", "enabled":true}]},
                "hotspot":{"enabled":false}
            }]
        }
    });
    let (routeros_plan, routeros_plan_errors, _routeros_plan_warnings) = build_routeros_collector_plan_payload(&routeros_plan_payload);
    let routeros_plan_ok = routeros_plan_errors.is_empty()
        && routeros_plan.get("command_count").and_then(Value::as_u64).unwrap_or(0) >= 5;
    checks.push(check("routeros_collector_plan_builder", routeros_plan_ok, json!({"command_count": routeros_plan.get("command_count"), "status": routeros_plan.get("status")})));
    if !routeros_plan_ok {
        errors.push(Diagnostic::error("self_test_routeros_plan_failed", Some("build-routeros-collector-plan".to_string()), "Self-test RouterOS collector plan should build deterministic PPPoE/DHCP read commands."));
    }

    let routeros_results_payload = json!({
        "plan": routeros_plan.clone(),
        "results": [
            {"router":"RB5009", "source":"pppoe", "path":"/ppp/active", "status":"ok", "rows":[{"name":"selftest", "address":"10.0.0.2"}], "duration_ms": 5.0},
            {"router":"RB5009", "source":"pppoe", "path":"/ppp/secret", "status":"ok", "rows":[{"name":"selftest", "profile":"15M"}], "duration_ms": 5.0},
            {"router":"RB5009", "source":"pppoe", "path":"/ppp/profile", "status":"ok", "rows":[{"name":"15M", "rate-limit":"15M/15M"}], "duration_ms": 5.0},
            {"router":"RB5009", "source":"dhcp", "path":"/ip/dhcp-server/lease", "status":"ok", "rows":[], "duration_ms": 5.0},
            {"router":"RB5009", "source":"dhcp", "path":"/ip/dhcp-server", "status":"ok", "rows":[{"name":"LAN"}], "duration_ms": 5.0}
        ]
    });
    let (routeros_results, routeros_results_errors, _routeros_results_warnings) = validate_routeros_read_results_payload(&routeros_results_payload);
    let routeros_results_ok = routeros_results_errors.is_empty()
        && routeros_results.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(false);
    checks.push(check("routeros_read_results_contract", routeros_results_ok, json!({"status": routeros_results.get("status"), "safe_for_cleanup": routeros_results.get("safe_for_cleanup")})));
    if !routeros_results_ok {
        errors.push(Diagnostic::error("self_test_routeros_results_failed", Some("validate-routeros-read-results".to_string()), "Self-test RouterOS read-result contract should trust complete planned command results."));
    }

    let transport_payload = json!({
        "config": {
            "routers": [{
                "name":"RB5009",
                "enabled": true,
                "address": "10.0.0.1",
                "username": "selftest",
                "password": "redacted-by-test",
                "pppoe":{"enabled":true},
                "dhcp":{"enabled":false},
                "hotspot":{"enabled":false}
            }]
        }
    });
    let (transport_result, transport_errors, _transport_warnings) = build_routeros_transport_session_payload(&transport_payload);
    let transport_ok = transport_errors.is_empty()
        && transport_result.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && transport_result.get("status").and_then(Value::as_str) == Some("ready_for_future_transport");
    checks.push(check("routeros_transport_session_rehearsal", transport_ok, json!({"status": transport_result.get("status"), "connection_attempt_count": transport_result.get("connection_attempt_count")})));
    if !transport_ok {
        errors.push(Diagnostic::error("self_test_routeros_transport_failed", Some("build-routeros-transport-session".to_string()), "Self-test RouterOS transport session rehearsal should not attempt live connections and should report ready_for_future_transport."));
    }

    let live_pilot_payload = json!({
        "router": "RB5009",
        "source": "pppoe",
        "config": {
            "routers": [{
                "name":"RB5009",
                "enabled": true,
                "address": "10.0.0.1",
                "username": "selftest",
                "password": "redacted-by-test",
                "pppoe":{"enabled":true},
                "dhcp":{"enabled":false},
                "hotspot":{"enabled":false}
            }]
        }
    });
    let (live_pilot, live_pilot_errors, _live_pilot_warnings) = build_routeros_live_read_pilot_payload(&live_pilot_payload);
    let live_pilot_ok = live_pilot_errors.is_empty()
        && live_pilot.get("status").and_then(Value::as_str) == Some("pilot_contract_ready")
        && live_pilot.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_live_read_pilot_contract", live_pilot_ok, json!({"status": live_pilot.get("status"), "connection_attempt_count": live_pilot.get("connection_attempt_count")})));
    if !live_pilot_ok {
        errors.push(Diagnostic::error("self_test_routeros_live_pilot_failed", Some("build-routeros-live-read-pilot".to_string()), "Self-test RouterOS live-read pilot contract should select one command without attempting a connection."));
    }

    let read_pilot_payload = json!({
        "adapter": "fixture",
        "execute": true,
        "router": "RB5009",
        "source": "pppoe",
        "path": "/ppp/active",
        "fixture_rows": [{"name":"selftest", "address":"10.0.0.2"}],
        "config": {
            "routers": [{
                "name":"RB5009",
                "enabled": true,
                "address": "10.0.0.1",
                "username": "selftest",
                "password": "redacted-by-test",
                "pppoe":{"enabled":true},
                "dhcp":{"enabled":false},
                "hotspot":{"enabled":false}
            }]
        }
    });
    let (read_pilot, read_pilot_errors, _read_pilot_warnings) = run_routeros_read_pilot_payload(&read_pilot_payload);
    let read_pilot_ok = read_pilot_errors.is_empty()
        && read_pilot.get("status").and_then(Value::as_str) == Some("fixture_executed")
        && read_pilot.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && read_pilot.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(false);
    checks.push(check("routeros_read_pilot_fixture", read_pilot_ok, json!({"status": read_pilot.get("status"), "row_count": read_pilot.get("row_count"), "connection_attempt_count": read_pilot.get("connection_attempt_count")})));
    if !read_pilot_ok {
        errors.push(Diagnostic::error("self_test_routeros_read_pilot_failed", Some("run-routeros-read-pilot".to_string()), "Self-test RouterOS read pilot fixture should execute offline without attempting a connection."));
    }

    let collector_bundle_payload = json!({
        "router": {"name":"RB5009", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
        "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
        "pppoe": {
            "active": [{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
            "secrets": [{"name":"selftest", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
            "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
        }
    });
    let (collector_bundle, collector_bundle_errors, _collector_bundle_warnings) = build_collector_circuit_bundle_payload(&collector_bundle_payload);
    let collector_bundle_ok = collector_bundle_errors.is_empty() && collector_bundle.get("normalized_count").and_then(Value::as_u64).unwrap_or(0) == 1;
    checks.push(check("collector_bundle_shadow_builder", collector_bundle_ok, json!({"normalized_count": collector_bundle.get("normalized_count"), "mode": collector_bundle.get("mode")})));
    if !collector_bundle_ok {
        errors.push(Diagnostic::error("self_test_collector_bundle_failed", Some("build-collector-circuit-bundle".to_string()), "Self-test collector bundle should build one PPP circuit row in shadow mode."));
    }

    let collector_rows = collector_bundle.get("normalized_rows").cloned().unwrap_or_else(|| json!([]));
    let (collector_parity, collector_parity_errors, _collector_parity_warnings) = compare_collector_bundle_parity_payload(&json!({
        "python_rows": collector_rows.clone(),
        "rust_rows": collector_rows.clone()
    }));
    let collector_parity_ok = collector_parity_errors.is_empty()
        && collector_parity.get("verdict").and_then(Value::as_str).unwrap_or("") == "parity_pass";
    checks.push(check("collector_bundle_parity_shadow", collector_parity_ok, json!({"verdict": collector_parity.get("verdict"), "parity_score": collector_parity.get("parity_score")})));
    if !collector_parity_ok {
        errors.push(Diagnostic::error("self_test_collector_parity_failed", Some("compare-collector-bundle-parity".to_string()), "Self-test collector parity should pass when Python and Rust rows are identical."));
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

    let (rollback_execute, rollback_execute_errors, _rollback_execute_warnings) = execute_rollback_payload(&json!({
        "rollback_manifest": rollback_from_journal.clone(),
        "execute": false,
        "allow_rollback_file_writes": false
    }));
    let rollback_execute_ok = rollback_execute_errors.is_empty() && rollback_execute.get("executed").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("rollback_execute_rehearsal", rollback_execute_ok, json!({"status": rollback_execute.get("status"), "executed": rollback_execute.get("executed")})));
    if !rollback_execute_ok {
        errors.push(Diagnostic::error("self_test_rollback_execute_failed", Some("execute-rollback".to_string()), "Self-test rollback execution rehearsal should not restore files."));
    }
    let _ = std::fs::remove_file(temp_journal_path);


    let (authority_readiness, authority_readiness_errors, _authority_readiness_warnings) = evaluate_authority_readiness_payload(&json!({
        "config": {
            "rust_core": {"enabled": true, "authority_mode": "shadow"},
            "paths": {"shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv", "network_json": "/opt/libreqos/src/network.json", "transaction_journal": "/opt/lqosync/logs/transaction_journal.jsonl"}
        },
        "rust_core_status": {"available": true, "ok": true},
        "self_test": {"ok": true, "result": {"status": "ok"}}
    }));
    let authority_readiness_ok = authority_readiness_errors.is_empty() && authority_readiness.get("verdict").and_then(Value::as_str).unwrap_or("") == "shadow_safe";
    checks.push(check("authority_readiness_shadow_safe", authority_readiness_ok, json!({"verdict": authority_readiness.get("verdict"), "risk_level": authority_readiness.get("risk_level")})));
    if !authority_readiness_ok {
        errors.push(Diagnostic::error("self_test_authority_readiness_failed", Some("evaluate-authority-readiness".to_string()), "Self-test authority readiness should report shadow_safe for default shadow mode."));
    }


    let (full_readiness, full_readiness_errors, _full_readiness_warnings) = evaluate_full_rust_readiness_payload(&json!({
        "config": {
            "rust_core": {"enabled": true, "authority_mode": "shadow"},
            "paths": {"shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv", "network_json": "/opt/libreqos/src/network.json", "transaction_journal": "/opt/lqosync/logs/transaction_journal.jsonl"}
        },
        "rust_core_status": {"available": true, "ok": true},
        "self_test": {"ok": true, "result": {"status": "ok", "operations": operations}},
        "authority_readiness": {"result": authority_readiness.clone()}
    }));
    let full_readiness_ok = full_readiness_errors.is_empty()
        && full_readiness.get("full_backend_ready").and_then(Value::as_bool).unwrap_or(true) == false
        && full_readiness.get("verdict").and_then(Value::as_str).unwrap_or("") == "not_full_rust_backend_yet";
    checks.push(check("full_rust_readiness_reports_hybrid", full_readiness_ok, json!({"verdict": full_readiness.get("verdict"), "maturity": full_readiness.get("maturity")})));
    if !full_readiness_ok {
        errors.push(Diagnostic::error("self_test_full_rust_readiness_failed", Some("evaluate-full-rust-readiness".to_string()), "Self-test full Rust readiness should report hybrid/not full backend yet."));
    }

    let (pilot_plan, pilot_plan_errors, _pilot_plan_warnings) = build_authority_pilot_plan_payload(&json!({
        "config": {"rust_core": {"enabled": true, "authority_mode": "shadow"}},
        "authority_readiness": {"result": authority_readiness.clone()},
        "full_backend_readiness": {"result": full_readiness.clone()}
    }));
    let pilot_plan_ok = pilot_plan_errors.is_empty()
        && pilot_plan.get("pilot_only").and_then(Value::as_bool).unwrap_or(false)
        && pilot_plan.get("stages").and_then(Value::as_array).map(|v| v.len() >= 6).unwrap_or(false);
    checks.push(check("authority_pilot_plan_available", pilot_plan_ok, json!({"pilot_only": pilot_plan.get("pilot_only"), "stage_count": pilot_plan.get("stages").and_then(Value::as_array).map(|v| v.len()).unwrap_or(0)})));
    if !pilot_plan_ok {
        errors.push(Diagnostic::error("self_test_authority_pilot_plan_failed", Some("build-authority-pilot-plan".to_string()), "Self-test authority pilot plan should produce ordered non-mutating stages."));
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
        assert!(ops.contains(&OP_EXECUTE_ROLLBACK));
        assert!(ops.contains(&OP_BUILD_ROUTEROS_COLLECTOR_PLAN));
        assert!(ops.contains(&OP_VALIDATE_ROUTEROS_READ_RESULTS));
        assert!(ops.contains(&OP_BUILD_ROUTEROS_TRANSPORT_SESSION));
        assert!(ops.contains(&OP_BUILD_ROUTEROS_LIVE_READ_PILOT));
        assert!(ops.contains(&OP_BUILD_COLLECTOR_CIRCUIT_BUNDLE));
        assert!(ops.contains(&OP_COMPARE_COLLECTOR_BUNDLE_PARITY));
        assert!(ops.contains(&OP_EVALUATE_AUTHORITY_READINESS));
        assert!(ops.contains(&OP_SELF_TEST));
    }
}
