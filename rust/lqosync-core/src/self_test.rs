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
use crate::routeros_api_codec::build_routeros_api_sentence_payload;
use crate::routeros_api_reply::decode_routeros_api_reply_payload;
use crate::routeros_api_frame::codec_routeros_api_frame_payload;
use crate::routeros_offline_session::run_routeros_offline_session_payload;
use crate::routeros_tcp_probe::run_routeros_tcp_connectivity_pilot_payload;
use crate::routeros_auth_plan::build_routeros_auth_plan_payload;
use crate::routeros_auth_handshake::run_routeros_auth_handshake_payload;
use crate::routeros_auth_session::build_routeros_auth_session_contract_payload;
use crate::routeros_authenticated_read::run_routeros_authenticated_read_fixture_payload;
use crate::routeros_live_read_adapter::run_routeros_live_read_adapter_pilot_payload;
use crate::collector_authority_pilot::evaluate_rust_collector_authority_pilot_payload;
use crate::collector_authority_manifest::build_collector_authority_manifest_payload;
use crate::collector_authority_selection::build_collector_authority_selection_payload;
use crate::collector_authority_dry_run::build_collector_authority_dry_run_bundle_payload;
use crate::collector_run_cycle_shadow::build_run_cycle_rust_shadow_report_payload;
use crate::collector_authority_activation::build_collector_authority_activation_plan_payload;
use crate::collector_authority_runtime::build_collector_authority_runtime_contract_payload;
use crate::collector_authority_switch::build_collector_authority_switch_rehearsal_payload;
use crate::collector_authority_pilot_execution::build_collector_authority_pilot_execution_contract_payload;
use crate::collector_authority_pilot_result::evaluate_collector_authority_pilot_result_payload;
use crate::collector_authority_promotion::build_collector_authority_promotion_readiness_payload;
use crate::collector_authority_promotion_execution::build_collector_authority_promotion_execution_rehearsal_payload;
use crate::collector_authority_promotion_commit::build_collector_authority_promotion_commit_plan_payload;
use crate::collector_authority_promotion_cutover::build_collector_authority_promotion_cutover_ledger_payload;
use crate::collector_authority_production_freeze::build_collector_authority_production_freeze_gate_payload;
use crate::collector_authority_production_switch::build_collector_authority_production_switch_contract_payload;
use crate::rust_backend_api_handoff::build_rust_backend_api_handoff_plan_payload;
use crate::rust_backend_scheduler_handoff::build_rust_backend_scheduler_handoff_plan_payload;
use crate::rust_run_cycle_orchestrator_handoff::build_rust_run_cycle_orchestrator_handoff_contract_payload;
use crate::rust_config_state_authority_handoff::build_rust_config_state_authority_handoff_contract_payload;
use crate::rust_live_collector_authority_handoff::build_rust_live_collector_authority_handoff_contract_payload;
use crate::rust_circuit_builder_authority_handoff::build_rust_circuit_builder_authority_handoff_contract_payload;
use crate::rust_sync_engine_authority_handoff::build_rust_sync_engine_authority_handoff_contract_payload;
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
pub const OP_BUILD_ROUTEROS_API_SENTENCE: &str = "build-routeros-api-sentence";
pub const OP_DECODE_ROUTEROS_API_REPLY: &str = "decode-routeros-api-reply";
pub const OP_CODEC_ROUTEROS_API_FRAME: &str = "codec-routeros-api-frame";
pub const OP_RUN_ROUTEROS_OFFLINE_SESSION: &str = "run-routeros-offline-session";
pub const OP_RUN_ROUTEROS_TCP_CONNECTIVITY_PILOT: &str = "run-routeros-tcp-connectivity-pilot";
pub const OP_BUILD_ROUTEROS_AUTH_PLAN: &str = "build-routeros-auth-plan";
pub const OP_RUN_ROUTEROS_AUTH_HANDSHAKE: &str = "run-routeros-auth-handshake";
pub const OP_BUILD_ROUTEROS_AUTH_SESSION_CONTRACT: &str = "build-routeros-auth-session-contract";
pub const OP_RUN_ROUTEROS_AUTHENTICATED_READ_FIXTURE: &str = "run-routeros-authenticated-read-fixture";
pub const OP_RUN_ROUTEROS_LIVE_READ_ADAPTER_PILOT: &str = "run-routeros-live-read-adapter-pilot";
pub const OP_EVALUATE_RUST_COLLECTOR_AUTHORITY_PILOT: &str = "evaluate-rust-collector-authority-pilot";
pub const OP_BUILD_COLLECTOR_AUTHORITY_MANIFEST: &str = "build-collector-authority-manifest";
pub const OP_BUILD_COLLECTOR_AUTHORITY_SELECTION: &str = "build-collector-authority-selection";
pub const OP_BUILD_COLLECTOR_AUTHORITY_DRY_RUN_BUNDLE: &str = "build-collector-authority-dry-run-bundle";
pub const OP_BUILD_RUN_CYCLE_RUST_SHADOW_REPORT: &str = "build-run-cycle-rust-shadow-report";
pub const OP_BUILD_COLLECTOR_AUTHORITY_ACTIVATION_PLAN: &str = "build-collector-authority-activation-plan";
pub const OP_BUILD_COLLECTOR_AUTHORITY_RUNTIME_CONTRACT: &str = "build-collector-authority-runtime-contract";
pub const OP_BUILD_COLLECTOR_AUTHORITY_SWITCH_REHEARSAL: &str = "build-collector-authority-switch-rehearsal";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PILOT_EXECUTION_CONTRACT: &str = "build-collector-authority-pilot-execution-contract";
pub const OP_EVALUATE_COLLECTOR_AUTHORITY_PILOT_RESULT: &str = "evaluate-collector-authority-pilot-result";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_READINESS: &str = "build-collector-authority-promotion-readiness";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL: &str = "build-collector-authority-promotion-execution-rehearsal";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN: &str = "build-collector-authority-promotion-commit-plan";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER: &str = "build-collector-authority-promotion-cutover-ledger";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE: &str = "build-collector-authority-production-freeze-gate";
pub const OP_BUILD_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT: &str = "build-collector-authority-production-switch-contract";
pub const OP_BUILD_RUST_BACKEND_API_HANDOFF_PLAN: &str = "build-rust-backend-api-handoff-plan";
pub const OP_BUILD_RUST_BACKEND_SCHEDULER_HANDOFF_PLAN: &str = "build-rust-backend-scheduler-handoff-plan";
pub const OP_BUILD_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT: &str = "build-rust-run-cycle-orchestrator-handoff-contract";
pub const OP_BUILD_RUST_CONFIG_STATE_AUTHORITY_HANDOFF_CONTRACT: &str = "build-rust-config-state-authority-handoff-contract";
pub const OP_BUILD_RUST_LIVE_COLLECTOR_AUTHORITY_HANDOFF_CONTRACT: &str = "build-rust-live-collector-authority-handoff-contract";
pub const OP_BUILD_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT: &str = "build-rust-circuit-builder-authority-handoff-contract";
pub const OP_BUILD_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT: &str = "build-rust-sync-engine-authority-handoff-contract";
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
        OP_BUILD_ROUTEROS_API_SENTENCE,
        OP_DECODE_ROUTEROS_API_REPLY,
        OP_CODEC_ROUTEROS_API_FRAME,
        OP_RUN_ROUTEROS_OFFLINE_SESSION,
        OP_RUN_ROUTEROS_TCP_CONNECTIVITY_PILOT,
        OP_BUILD_ROUTEROS_AUTH_PLAN,
        OP_RUN_ROUTEROS_AUTH_HANDSHAKE,
        OP_BUILD_ROUTEROS_AUTH_SESSION_CONTRACT,
        OP_RUN_ROUTEROS_AUTHENTICATED_READ_FIXTURE,
        OP_RUN_ROUTEROS_LIVE_READ_ADAPTER_PILOT,
        OP_EVALUATE_RUST_COLLECTOR_AUTHORITY_PILOT,
        OP_BUILD_COLLECTOR_AUTHORITY_MANIFEST,
        OP_BUILD_COLLECTOR_AUTHORITY_SELECTION,
        OP_BUILD_COLLECTOR_AUTHORITY_DRY_RUN_BUNDLE,
        OP_BUILD_RUN_CYCLE_RUST_SHADOW_REPORT,
        OP_BUILD_COLLECTOR_AUTHORITY_ACTIVATION_PLAN,
        OP_BUILD_COLLECTOR_AUTHORITY_RUNTIME_CONTRACT,
        OP_BUILD_COLLECTOR_AUTHORITY_SWITCH_REHEARSAL,
        OP_BUILD_COLLECTOR_AUTHORITY_PILOT_EXECUTION_CONTRACT,
        OP_EVALUATE_COLLECTOR_AUTHORITY_PILOT_RESULT,
        OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_READINESS,
        OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL,
        OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN,
        OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER,
        OP_BUILD_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE,
        OP_BUILD_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT,
        OP_BUILD_RUST_BACKEND_API_HANDOFF_PLAN,
        OP_BUILD_RUST_BACKEND_SCHEDULER_HANDOFF_PLAN,
        OP_BUILD_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT,
        OP_BUILD_RUST_CONFIG_STATE_AUTHORITY_HANDOFF_CONTRACT,
        OP_BUILD_RUST_LIVE_COLLECTOR_AUTHORITY_HANDOFF_CONTRACT,
        OP_BUILD_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT,
        OP_BUILD_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT,
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

    let api_sentence_payload = json!({
        "path": "/ppp/active",
        "fields": ["name", "address", "caller-id"]
    });
    let (api_sentence, api_sentence_errors, _api_sentence_warnings) = build_routeros_api_sentence_payload(&api_sentence_payload);
    let api_sentence_ok = api_sentence_errors.is_empty()
        && api_sentence.get("status").and_then(Value::as_str) == Some("encoded")
        && api_sentence.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && api_sentence.get("sentence_words").and_then(Value::as_array).map(|v| !v.is_empty()).unwrap_or(false);
    checks.push(check("routeros_api_sentence_codec", api_sentence_ok, json!({"status": api_sentence.get("status"), "word_count": api_sentence.get("word_count"), "connection_attempt_count": api_sentence.get("connection_attempt_count")})));
    if !api_sentence_ok {
        errors.push(Diagnostic::error("self_test_routeros_api_sentence_failed", Some("build-routeros-api-sentence".to_string()), "Self-test RouterOS API sentence codec should encode a print command offline without attempting a connection."));
    }

    let api_reply_payload = json!({
        "words": ["!re", "=name=selftest", "=address=10.0.0.2", "!done"]
    });
    let (api_reply, api_reply_errors, _api_reply_warnings) = decode_routeros_api_reply_payload(&api_reply_payload);
    let api_reply_ok = api_reply_errors.is_empty()
        && api_reply.get("status").and_then(Value::as_str) == Some("decoded")
        && api_reply.get("row_count").and_then(Value::as_u64).unwrap_or(0) == 1
        && api_reply.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_api_reply_decoder", api_reply_ok, json!({"status": api_reply.get("status"), "row_count": api_reply.get("row_count"), "connection_attempt_count": api_reply.get("connection_attempt_count")})));
    if !api_reply_ok {
        errors.push(Diagnostic::error("self_test_routeros_api_reply_failed", Some("decode-routeros-api-reply".to_string()), "Self-test RouterOS API reply decoder should decode offline reply words without attempting a connection."));
    }

    let api_frame_payload = json!({
        "direction": "encode",
        "words": ["/ppp/active/print", "=.proplist=name,address"]
    });
    let (api_frame, api_frame_errors, _api_frame_warnings) = codec_routeros_api_frame_payload(&api_frame_payload);
    let api_frame_ok = api_frame_errors.is_empty()
        && api_frame.get("status").and_then(Value::as_str) == Some("frame_encoded")
        && api_frame.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && api_frame.get("zero_terminated").and_then(Value::as_bool).unwrap_or(false);
    checks.push(check("routeros_api_frame_codec", api_frame_ok, json!({"status": api_frame.get("status"), "byte_count": api_frame.get("byte_count"), "connection_attempt_count": api_frame.get("connection_attempt_count")})));
    if !api_frame_ok {
        errors.push(Diagnostic::error("self_test_routeros_api_frame_failed", Some("codec-routeros-api-frame".to_string()), "Self-test RouterOS API frame codec should encode offline frame bytes without attempting a connection."));
    }

    let offline_session_payload = json!({
        "path":"/ppp/active",
        "fields":["name", "address"],
        "fixture_rows":[{"name":"selftest", "address":"10.0.0.2"}]
    });
    let (offline_session, offline_session_errors, _offline_session_warnings) = run_routeros_offline_session_payload(&offline_session_payload);
    let offline_session_ok = offline_session_errors.is_empty()
        && offline_session.get("status").and_then(Value::as_str) == Some("offline_session_complete")
        && offline_session.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_offline_session_pipeline", offline_session_ok, json!({"status": offline_session.get("status"), "row_count": offline_session.get("row_count"), "connection_attempt_count": offline_session.get("connection_attempt_count")})));
    if !offline_session_ok {
        errors.push(Diagnostic::error("self_test_routeros_offline_session_failed", Some("run-routeros-offline-session".to_string()), "Self-test RouterOS offline session should round-trip command/reply frames using fixtures only without attempting a connection."));
    }

    let (tcp_probe, tcp_probe_errors, _tcp_probe_warnings) = run_routeros_tcp_connectivity_pilot_payload(&json!({
        "router": {"name": "selftest", "address": "127.0.0.1", "port": 8728},
        "execute": false
    }));
    let tcp_probe_ok = tcp_probe_errors.is_empty()
        && tcp_probe.get("status").and_then(Value::as_str) == Some("tcp_connect_rehearsal")
        && tcp_probe.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && tcp_probe.get("authentication_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_tcp_connectivity_rehearsal", tcp_probe_ok, json!({
        "status": tcp_probe.get("status"),
        "connection_attempt_count": tcp_probe.get("connection_attempt_count"),
        "authentication_attempt_count": tcp_probe.get("authentication_attempt_count")
    })));
    if !tcp_probe_ok {
        errors.push(Diagnostic::error("self_test_routeros_tcp_probe_failed", Some("run-routeros-tcp-connectivity-pilot".to_string()), "Self-test RouterOS TCP connectivity pilot should rehearse without attempting a connection."));
    }

    let (auth_plan, auth_plan_errors, _auth_plan_warnings) = build_routeros_auth_plan_payload(&json!({
        "router": {"name":"selftest", "address":"127.0.0.1", "port":8728, "username":"admin", "password":"selftest_secret"},
        "execute": false
    }));
    let auth_plan_ok = auth_plan_errors.is_empty()
        && auth_plan.get("status").and_then(Value::as_str) == Some("auth_plan_ready")
        && auth_plan.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && auth_plan.get("authentication_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_auth_plan_rehearsal", auth_plan_ok, json!({
        "status": auth_plan.get("status"),
        "connection_attempt_count": auth_plan.get("connection_attempt_count"),
        "authentication_attempt_count": auth_plan.get("authentication_attempt_count")
    })));
    if !auth_plan_ok {
        errors.push(Diagnostic::error("self_test_routeros_auth_plan_failed", Some("build-routeros-auth-plan".to_string()), "Self-test RouterOS auth plan should rehearse without emitting credentials or attempting authentication."));
    }

    let (auth_handshake, auth_handshake_errors, _auth_handshake_warnings) = run_routeros_auth_handshake_payload(&json!({
        "router": {"name":"selftest", "address":"127.0.0.1", "port":8728, "username":"admin", "password":"selftest_secret"},
        "adapter": "fixture",
        "execute": true,
        "fixture_reply_words": ["!done"]
    }));
    let auth_handshake_ok = auth_handshake_errors.is_empty()
        && auth_handshake.get("status").and_then(Value::as_str) == Some("auth_fixture_accepted")
        && auth_handshake.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && auth_handshake.get("authentication_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_auth_handshake_fixture", auth_handshake_ok, json!({
        "status": auth_handshake.get("status"),
        "connection_attempt_count": auth_handshake.get("connection_attempt_count"),
        "authentication_attempt_count": auth_handshake.get("authentication_attempt_count"),
        "fixture_handshake_count": auth_handshake.get("fixture_handshake_count")
    })));
    if !auth_handshake_ok {
        errors.push(Diagnostic::error("self_test_routeros_auth_handshake_failed", Some("run-routeros-auth-handshake".to_string()), "Self-test RouterOS auth handshake fixture should accept !done without opening sockets or emitting credentials."));
    }

    let auth_session_payload = json!({
        "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"redacted-by-test"},
        "adapter":"fixture",
        "execute": true,
        "fixture_reply_words": ["!done"]
    });
    let (auth_session, auth_session_errors, _auth_session_warnings) = build_routeros_auth_session_contract_payload(&auth_session_payload);
    let auth_session_ok = auth_session_errors.is_empty()
        && auth_session.get("status").and_then(Value::as_str) == Some("auth_session_contract_ready")
        && auth_session.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && auth_session.get("authenticated").and_then(Value::as_bool).unwrap_or(false);
    checks.push(check("routeros_auth_session_contract", auth_session_ok, json!({"status": auth_session.get("status"), "authenticated": auth_session.get("authenticated"), "connection_attempt_count": auth_session.get("connection_attempt_count")})));
    if !auth_session_ok {
        errors.push(Diagnostic::error("self_test_routeros_auth_session_failed", Some("build-routeros-auth-session-contract".to_string()), "Self-test RouterOS auth session contract should build an authenticated fixture session without network access."));
    }


    let authenticated_read_payload = json!({
        "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"redacted-by-test"},
        "adapter":"fixture",
        "execute": true,
        "fixture_reply_words": ["!done"],
        "path": "/ppp/active",
        "fields": ["name", "address"],
        "fixture_rows": [{"name":"selftest", "address":"10.0.0.2"}]
    });
    let (authenticated_read, authenticated_read_errors, _authenticated_read_warnings) = run_routeros_authenticated_read_fixture_payload(&authenticated_read_payload);
    let authenticated_read_ok = authenticated_read_errors.is_empty()
        && authenticated_read.get("status").and_then(Value::as_str) == Some("authenticated_read_fixture_complete")
        && authenticated_read.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && authenticated_read.get("row_count").and_then(Value::as_u64).unwrap_or(0) == 1;
    checks.push(check("routeros_authenticated_read_fixture", authenticated_read_ok, json!({
        "status": authenticated_read.get("status"),
        "connection_attempt_count": authenticated_read.get("connection_attempt_count"),
        "row_count": authenticated_read.get("row_count")
    })));
    if !authenticated_read_ok {
        errors.push(Diagnostic::error("self_test_routeros_authenticated_read_failed", Some("run-routeros-authenticated-read-fixture".to_string()), "Self-test authenticated read fixture should complete without network access."));
    }

    let live_read_adapter_payload = json!({
        "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"redacted-by-test"},
        "adapter":"contract",
        "mode":"contract",
        "execute": false,
        "fixture_reply_words": ["!done"],
        "path": "/ppp/active",
        "fields": ["name", "address"]
    });
    let (live_read_adapter, live_read_adapter_errors, _live_read_adapter_warnings) = run_routeros_live_read_adapter_pilot_payload(&live_read_adapter_payload);
    let live_read_adapter_ok = live_read_adapter_errors.is_empty()
        && live_read_adapter.get("status").and_then(Value::as_str) == Some("live_read_adapter_contract_ready")
        && live_read_adapter.get("connection_attempt_count").and_then(Value::as_u64).unwrap_or(1) == 0
        && live_read_adapter.get("api_sentence_write_count").and_then(Value::as_u64).unwrap_or(1) == 0;
    checks.push(check("routeros_live_read_adapter_contract", live_read_adapter_ok, json!({
        "status": live_read_adapter.get("status"),
        "connection_attempt_count": live_read_adapter.get("connection_attempt_count"),
        "api_sentence_write_count": live_read_adapter.get("api_sentence_write_count")
    })));
    if !live_read_adapter_ok {
        errors.push(Diagnostic::error("self_test_routeros_live_read_adapter_failed", Some("run-routeros-live-read-adapter-pilot".to_string()), "Self-test live read adapter contract should be ready without opening sockets or sending API words."));
    }

    let collector_authority_payload = json!({
        "router": {"name":"selftest", "address":"127.0.0.1", "username":"admin", "password":"selftest_secret"},
        "source": "pppoe",
        "path": "/ppp/active",
        "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
        "rust_core": {
            "allow_rust_collector_authority": true,
            "rust_collector_authority_pilot": true,
            "allow_rust_routeros_live_read_adapter": true,
            "routeros_live_read_adapter_pilot": true,
            "rust_collector_authority_sources": ["pppoe"],
            "collector_authority_mode": "rust_collector_authority_pilot"
        }
    });
    let (collector_authority, collector_authority_errors, _collector_authority_warnings) = evaluate_rust_collector_authority_pilot_payload(&collector_authority_payload);
    let collector_authority_ok = collector_authority_errors.is_empty()
        && collector_authority.get("status").and_then(Value::as_str) == Some("collector_authority_pilot_gate_ready")
        && collector_authority.get("gates_ready").and_then(Value::as_bool).unwrap_or(false)
        && collector_authority.get("full_rust_backend").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("rust_collector_authority_pilot_gate", collector_authority_ok, json!({
        "status": collector_authority.get("status"),
        "gates_ready": collector_authority.get("gates_ready"),
        "collector_authority": collector_authority.get("collector_authority")
    })));
    if !collector_authority_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_pilot_failed", Some("evaluate-rust-collector-authority-pilot".to_string()), "Self-test Rust collector authority pilot gate should become eligible only as a non-authoritative gate."));
    }

    let collector_manifest_payload = json!({
        "router": {"name":"selftest", "address":"127.0.0.1", "username":"admin", "password":"redacted-by-test"},
        "sources": ["pppoe"],
        "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
        "rust_core": {
            "allow_rust_collector_authority": true,
            "rust_collector_authority_pilot": true,
            "allow_rust_routeros_live_read_adapter": true,
            "routeros_live_read_adapter_pilot": true,
            "rust_collector_authority_sources": ["pppoe"],
            "collector_authority_mode": "rust_collector_authority_pilot"
        }
    });
    let (collector_manifest, collector_manifest_errors, _collector_manifest_warnings) = build_collector_authority_manifest_payload(&collector_manifest_payload);
    let collector_manifest_ok = collector_manifest_errors.is_empty()
        && collector_manifest.get("status").and_then(Value::as_str) == Some("collector_authority_manifest_ready")
        && collector_manifest.get("ready_count").and_then(Value::as_u64).unwrap_or(0) == 1
        && collector_manifest.get("full_rust_backend").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("collector_authority_decision_manifest", collector_manifest_ok, json!({
        "status": collector_manifest.get("status"),
        "ready_count": collector_manifest.get("ready_count"),
        "collector_authority": collector_manifest.get("collector_authority")
    })));
    if !collector_manifest_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_manifest_failed", Some("build-collector-authority-manifest".to_string()), "Self-test collector authority manifest should be ready when the source-level gate is ready."));
    }

    let collector_authority_selection_payload = json!({
        "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"redacted-by-test"},
        "sources": ["pppoe"],
        "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
        "rust_core": {
            "allow_rust_collector_authority": true,
            "rust_collector_authority_pilot": true,
            "allow_rust_routeros_live_read_adapter": true,
            "routeros_live_read_adapter_pilot": true,
            "rust_collector_authority_sources": ["pppoe"],
            "collector_authority_mode": "rust_collector_authority_pilot",
            "collector_authority_manifest_pilot": true,
            "allow_collector_authority_manifest": true,
            "collector_authority_dry_run_selection_pilot": true,
            "allow_collector_authority_dry_run_selection": true
        }
    });
    let (collector_authority_selection, collector_authority_selection_errors, _collector_authority_selection_warnings) = build_collector_authority_selection_payload(&collector_authority_selection_payload);
    let collector_authority_selection_ok = collector_authority_selection_errors.is_empty()
        && collector_authority_selection.get("status").and_then(Value::as_str) == Some("collector_authority_dry_run_selection_ready")
        && collector_authority_selection.get("rust_shadow_count").and_then(Value::as_u64).unwrap_or(0) >= 1
        && collector_authority_selection.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("collector_authority_dry_run_selection", collector_authority_selection_ok, json!({
        "status": collector_authority_selection.get("status"),
        "collector_authority": collector_authority_selection.get("collector_authority"),
        "rust_shadow_count": collector_authority_selection.get("rust_shadow_count")
    })));
    if !collector_authority_selection_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_selection_failed", Some("build-collector-authority-selection".to_string()), "Self-test collector authority dry-run selection should select Rust only as a shadow candidate while keeping Python production authority."));
    }

    let collector_authority_dry_run_payload = json!({
        "router": {"name":"RB5009", "address":"10.0.0.1", "port":8728, "username":"selftest", "password":"redacted-by-test", "pppoe":{"per_plan_node":true, "plan_node_name":"{profile}-{router}"}},
        "sources": ["pppoe"],
        "defaults": {"default_pppoe_rate":"10M/10M", "min_rate_percentage":0.5},
        "collector_parity": {"parity_score": 100.0, "verdict":"parity_pass"},
        "python_rows": [{"Circuit ID":"selftest", "Circuit Name":"selftest", "Device ID":"selftest", "Device Name":"selftest", "Parent Node":"15M-RB5009", "MAC":"AA:BB:CC:DD:EE:FF", "IPv4":"10.0.0.2", "IPv6":"", "Download Min Mbps":"7.5", "Upload Min Mbps":"7.5", "Download Max Mbps":"15", "Upload Max Mbps":"15", "Comment":"PPP"}],
        "pppoe": {
            "active": [{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}],
            "secrets": [{"name":"selftest", "profile":"15M", "comment":"PLAN|15M/15M", "disabled":"false", "inactive":"false"}],
            "profiles": [{"name":"15M", "rate-limit":"15M/15M"}]
        },
        "rust_core": {
            "allow_rust_collector_authority": true,
            "rust_collector_authority_pilot": true,
            "allow_rust_routeros_live_read_adapter": true,
            "routeros_live_read_adapter_pilot": true,
            "rust_collector_authority_sources": ["pppoe"],
            "collector_authority_mode": "rust_collector_authority_pilot",
            "collector_authority_manifest_pilot": true,
            "allow_collector_authority_manifest": true,
            "collector_authority_dry_run_selection_pilot": true,
            "allow_collector_authority_dry_run_selection": true,
            "collector_authority_dry_run_bundle_pilot": true,
            "allow_collector_authority_dry_run_bundle": true
        }
    });
    let (collector_authority_dry_run, collector_authority_dry_run_errors, _collector_authority_dry_run_warnings) = build_collector_authority_dry_run_bundle_payload(&collector_authority_dry_run_payload);
    let collector_authority_dry_run_ok = collector_authority_dry_run_errors.is_empty()
        && collector_authority_dry_run.get("status").and_then(Value::as_str) == Some("collector_authority_dry_run_bundle_ready")
        && collector_authority_dry_run.get("normalized_count").and_then(Value::as_u64).unwrap_or(0) == 1
        && collector_authority_dry_run.get("collector_output_can_drive_cleanup").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("collector_authority_dry_run_bundle", collector_authority_dry_run_ok, json!({
        "status": collector_authority_dry_run.get("status"),
        "normalized_count": collector_authority_dry_run.get("normalized_count"),
        "collector_authority": collector_authority_dry_run.get("collector_authority")
    })));
    if !collector_authority_dry_run_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_dry_run_failed", Some("build-collector-authority-dry-run-bundle".to_string()), "Self-test collector authority dry-run bundle should build one Rust-shadow bundle while keeping Python cleanup/apply authority."));
    }

    let mut run_cycle_shadow_payload = collector_authority_dry_run_payload.clone();
    if let Some(obj) = run_cycle_shadow_payload.as_object_mut() {
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("run_cycle_rust_shadow_report_enabled".to_string(), json!(true));
            rc.insert("run_cycle_rust_shadow_report_pilot".to_string(), json!(true));
        }
    }
    let (run_cycle_shadow, run_cycle_shadow_errors, _run_cycle_shadow_warnings) = build_run_cycle_rust_shadow_report_payload(&run_cycle_shadow_payload);
    let run_cycle_shadow_ok = run_cycle_shadow_errors.is_empty()
        && run_cycle_shadow.get("status").and_then(Value::as_str) == Some("run_cycle_rust_shadow_ready")
        && run_cycle_shadow.get("rust_row_count").and_then(Value::as_u64).unwrap_or(0) == 1
        && run_cycle_shadow.get("python_run_cycle_authoritative").and_then(Value::as_bool).unwrap_or(false)
        && run_cycle_shadow.get("rust_can_drive_cleanup").and_then(Value::as_bool).unwrap_or(true) == false;
    checks.push(check("run_cycle_rust_shadow_report", run_cycle_shadow_ok, json!({
        "status": run_cycle_shadow.get("status"),
        "rust_row_count": run_cycle_shadow.get("rust_row_count"),
        "python_run_cycle_authoritative": run_cycle_shadow.get("python_run_cycle_authoritative")
    })));
    if !run_cycle_shadow_ok {
        errors.push(Diagnostic::error("self_test_run_cycle_rust_shadow_failed", Some("build-run-cycle-rust-shadow-report".to_string()), "Self-test run_cycle Rust-shadow report should expose one Rust-shadow candidate while keeping Python run_cycle authoritative."));
    }

    let mut activation_payload = run_cycle_shadow_payload.clone();
    if let Some(obj) = activation_payload.as_object_mut() {
        obj.insert("successful_shadow_cycles".to_string(), json!(3));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_activation_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_activation".to_string(), json!(true));
            rc.insert("collector_authority_activation_mode".to_string(), json!("rust_collector_authority_pilot"));
            rc.insert("collector_authority_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_min_shadow_cycles".to_string(), json!(3));
        }
    }
    let (activation_plan, activation_errors, _activation_warnings) = build_collector_authority_activation_plan_payload(&activation_payload);
    let activation_ok = activation_errors.is_empty()
        && activation_plan.get("status").and_then(Value::as_str) == Some("collector_authority_activation_ready_for_pilot")
        && activation_plan.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_activation_plan", activation_ok, json!({
        "status": activation_plan.get("status"),
        "collector_authority": activation_plan.get("collector_authority"),
        "successful_shadow_cycles": activation_plan.get("successful_shadow_cycles")
    })));
    if !activation_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_activation_failed", Some("build-collector-authority-activation-plan".to_string()), "Self-test collector authority activation plan should become ready only as a non-mutating pilot with Python fallback retained."));
    }

    let mut runtime_payload = activation_payload.clone();
    if let Some(obj) = runtime_payload.as_object_mut() {
        obj.insert("shadow_age_seconds".to_string(), json!(30));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_runtime_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_runtime_contract".to_string(), json!(true));
            rc.insert("collector_authority_runtime_mode".to_string(), json!("rust_collector_authority_runtime_contract"));
            rc.insert("collector_authority_runtime_require_activation_plan".to_string(), json!(true));
            rc.insert("collector_authority_runtime_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_runtime_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (runtime_contract, runtime_errors, _runtime_warnings) = build_collector_authority_runtime_contract_payload(&runtime_payload);
    let runtime_ok = runtime_errors.is_empty()
        && runtime_contract.get("status").and_then(Value::as_str) == Some("collector_authority_runtime_contract_ready")
        && runtime_contract.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && runtime_contract.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_runtime_contract", runtime_ok, json!({
        "status": runtime_contract.get("status"),
        "collector_authority": runtime_contract.get("collector_authority"),
        "runtime_contract_only": runtime_contract.get("runtime_contract_only")
    })));
    if !runtime_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_runtime_failed", Some("build-collector-authority-runtime-contract".to_string()), "Self-test collector authority runtime contract should become ready only as a non-mutating pilot with Python fallback retained."));
    }

    let mut switch_payload = runtime_payload.clone();
    if let Some(obj) = switch_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_switch_rehearsal_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_switch_rehearsal".to_string(), json!(true));
            rc.insert("collector_authority_switch_mode".to_string(), json!("rust_collector_authority_switch_rehearsal"));
            rc.insert("collector_authority_switch_require_runtime_contract".to_string(), json!(true));
            rc.insert("collector_authority_switch_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_switch_require_manual_confirmation".to_string(), json!(true));
        }
    }
    let (switch_rehearsal, switch_errors, _switch_warnings) = build_collector_authority_switch_rehearsal_payload(&switch_payload);
    let switch_ok = switch_errors.is_empty()
        && switch_rehearsal.get("status").and_then(Value::as_str) == Some("collector_authority_switch_rehearsal_ready")
        && switch_rehearsal.get("collector_authority_switch_executed").and_then(Value::as_bool) == Some(false)
        && switch_rehearsal.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && switch_rehearsal.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_switch_rehearsal", switch_ok, json!({
        "status": switch_rehearsal.get("status"),
        "collector_authority": switch_rehearsal.get("collector_authority"),
        "switch_rehearsal_only": switch_rehearsal.get("switch_rehearsal_only")
    })));
    if !switch_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_switch_failed", Some("build-collector-authority-switch-rehearsal".to_string()), "Self-test collector authority switch rehearsal should be ready but non-mutating."));
    }


    let mut pilot_execution_payload = switch_payload.clone();
    if let Some(obj) = pilot_execution_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION"));
        obj.insert("collector_authority_switch_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_pilot_execution_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_pilot_execution_contract".to_string(), json!(true));
            rc.insert("collector_authority_pilot_execution_mode".to_string(), json!("rust_collector_authority_pilot_execution_contract"));
            rc.insert("collector_authority_pilot_execution_require_switch_rehearsal".to_string(), json!(true));
            rc.insert("collector_authority_pilot_execution_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_pilot_execution_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_pilot_execution_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (pilot_execution, pilot_execution_errors, _pilot_execution_warnings) = build_collector_authority_pilot_execution_contract_payload(&pilot_execution_payload);
    let pilot_execution_ok = pilot_execution_errors.is_empty()
        && pilot_execution.get("status").and_then(Value::as_str) == Some("collector_authority_pilot_execution_contract_ready")
        && pilot_execution.get("collector_authority_pilot_execution_executed").and_then(Value::as_bool) == Some(false)
        && pilot_execution.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && pilot_execution.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_pilot_execution_contract", pilot_execution_ok, json!({
        "status": pilot_execution.get("status"),
        "collector_authority": pilot_execution.get("collector_authority"),
        "pilot_execution_contract_only": pilot_execution.get("pilot_execution_contract_only")
    })));
    if !pilot_execution_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_pilot_execution_failed", Some("build-collector-authority-pilot-execution-contract".to_string()), "Self-test collector authority pilot execution contract should be ready but non-mutating."));
    }

    let mut pilot_result_payload = pilot_execution_payload.clone();
    if let Some(obj) = pilot_result_payload.as_object_mut() {
        let pilot_python_rows = obj.get("python_rows").cloned().unwrap_or_else(|| json!([]));
        obj.insert("pilot_result".to_string(), json!({
            "status":"pilot_shadow_complete",
            "rust_rows": pilot_python_rows.clone(),
            "python_rows": pilot_python_rows.clone(),
            "cleanup_attempted": false,
            "apply_attempted": false,
            "write_attempted": false,
            "error_count": 0
        }));
        obj.insert("rust_rows".to_string(), pilot_python_rows);
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_pilot_result_evaluator_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_pilot_result_evaluation".to_string(), json!(true));
            rc.insert("collector_authority_pilot_result_mode".to_string(), json!("rust_collector_authority_pilot_result_evaluation"));
            rc.insert("collector_authority_pilot_result_require_execution_contract".to_string(), json!(true));
            rc.insert("collector_authority_pilot_result_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_pilot_result_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_pilot_result_require_parity".to_string(), json!(true));
            rc.insert("collector_authority_pilot_result_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (pilot_result, pilot_result_errors, _pilot_result_warnings) = evaluate_collector_authority_pilot_result_payload(&pilot_result_payload);
    let pilot_result_ok = pilot_result_errors.is_empty()
        && pilot_result.get("status").and_then(Value::as_str) == Some("collector_authority_pilot_result_pass")
        && pilot_result.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && pilot_result.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_pilot_result_evaluation", pilot_result_ok, json!({
        "status": pilot_result.get("status"),
        "collector_authority": pilot_result.get("collector_authority"),
        "pilot_result_evaluated": pilot_result.get("collector_authority_pilot_result_evaluated")
    })));
    if !pilot_result_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_pilot_result_failed", Some("evaluate-collector-authority-pilot-result".to_string()), "Self-test collector authority pilot result evaluation should pass only as a non-mutating review result."));
    }

    let mut promotion_payload = pilot_result_payload.clone();
    if let Some(obj) = promotion_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS"));
        obj.insert("collector_authority_pilot_result_evaluation".to_string(), json!(pilot_result.clone()));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_promotion_readiness_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_promotion_readiness".to_string(), json!(true));
            rc.insert("collector_authority_promotion_readiness_mode".to_string(), json!("rust_collector_authority_promotion_readiness"));
            rc.insert("collector_authority_promotion_require_pilot_result".to_string(), json!(true));
            rc.insert("collector_authority_promotion_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_promotion_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_promotion_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_promotion_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (promotion_readiness, promotion_errors, _promotion_warnings) = build_collector_authority_promotion_readiness_payload(&promotion_payload);
    let promotion_ok = promotion_errors.is_empty()
        && promotion_readiness.get("status").and_then(Value::as_str) == Some("collector_authority_promotion_readiness_ready")
        && promotion_readiness.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && promotion_readiness.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_promotion_readiness", promotion_ok, json!({
        "status": promotion_readiness.get("status"),
        "collector_authority": promotion_readiness.get("collector_authority"),
        "promotion_ready": promotion_readiness.get("promotion_ready")
    })));
    if !promotion_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_promotion_readiness_failed", Some("build-collector-authority-promotion-readiness".to_string()), "Self-test collector authority promotion readiness should report ready only as a non-mutating review result."));
    }

    let mut promotion_execution_payload = promotion_payload.clone();
    if let Some(obj) = promotion_execution_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL"));
        obj.insert("collector_authority_promotion_readiness".to_string(), json!(promotion_readiness.clone()));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_promotion_execution_rehearsal_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_promotion_execution_rehearsal".to_string(), json!(true));
            rc.insert("collector_authority_promotion_execution_mode".to_string(), json!("rehearsal_only"));
            rc.insert("collector_authority_promotion_execution_require_readiness".to_string(), json!(true));
            rc.insert("collector_authority_promotion_execution_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_promotion_execution_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_promotion_execution_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_promotion_execution_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (promotion_execution, promotion_execution_errors, _promotion_execution_warnings) = build_collector_authority_promotion_execution_rehearsal_payload(&promotion_execution_payload);
    let promotion_execution_ok = promotion_execution_errors.is_empty()
        && promotion_execution.get("status").and_then(Value::as_str) == Some("collector_authority_promotion_execution_rehearsal_ready")
        && promotion_execution.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && promotion_execution.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_promotion_execution_rehearsal", promotion_execution_ok, json!({
        "status": promotion_execution.get("status"),
        "collector_authority": promotion_execution.get("collector_authority"),
        "promotion_execution_rehearsal_ready": promotion_execution.get("promotion_execution_rehearsal_ready")
    })));
    if !promotion_execution_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_promotion_execution_failed", Some("build-collector-authority-promotion-execution-rehearsal".to_string()), "Self-test collector authority promotion execution rehearsal should report ready only as a non-mutating rehearsal result."));
    }

    let mut promotion_commit_payload = promotion_execution_payload.clone();
    if let Some(obj) = promotion_commit_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN"));
        obj.insert("collector_authority_promotion_execution_rehearsal".to_string(), json!(promotion_execution.clone()));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_promotion_commit_plan_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_promotion_commit_plan".to_string(), json!(true));
            rc.insert("collector_authority_promotion_commit_mode".to_string(), json!("plan_only"));
            rc.insert("collector_authority_promotion_commit_require_execution_rehearsal".to_string(), json!(true));
            rc.insert("collector_authority_promotion_commit_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_promotion_commit_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_promotion_commit_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_promotion_commit_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (promotion_commit, promotion_commit_errors, _promotion_commit_warnings) = build_collector_authority_promotion_commit_plan_payload(&promotion_commit_payload);
    let promotion_commit_ok = promotion_commit_errors.is_empty()
        && promotion_commit.get("status").and_then(Value::as_str) == Some("collector_authority_promotion_commit_plan_ready")
        && promotion_commit.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && promotion_commit.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_promotion_commit_plan", promotion_commit_ok, json!({
        "status": promotion_commit.get("status"),
        "collector_authority": promotion_commit.get("collector_authority"),
        "promotion_commit_plan_ready": promotion_commit.get("promotion_commit_plan_ready")
    })));
    if !promotion_commit_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_promotion_commit_failed", Some("build-collector-authority-promotion-commit-plan".to_string()), "Self-test collector authority promotion commit plan should report ready only as a non-mutating planning result."));
    }

    let mut promotion_cutover_payload = promotion_commit_payload.clone();
    if let Some(obj) = promotion_cutover_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER"));
        obj.insert("collector_authority_promotion_commit_confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN"));
        obj.insert("rollback_path".to_string(), json!("python_fallback_revert"));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_promotion_cutover_ledger_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_promotion_cutover_ledger".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_mode".to_string(), json!("ledger_only"));
            rc.insert("collector_authority_promotion_cutover_require_commit_plan".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_require_rollback_path".to_string(), json!(true));
            rc.insert("collector_authority_promotion_cutover_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (promotion_cutover, promotion_cutover_errors, _promotion_cutover_warnings) = build_collector_authority_promotion_cutover_ledger_payload(&promotion_cutover_payload);
    let promotion_cutover_ok = promotion_cutover_errors.is_empty()
        && promotion_cutover.get("status").and_then(Value::as_str) == Some("collector_authority_promotion_cutover_ledger_ready")
        && promotion_cutover.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && promotion_cutover.get("rust_can_drive_cleanup").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_promotion_cutover_ledger", promotion_cutover_ok, json!({
        "status": promotion_cutover.get("status"),
        "collector_authority": promotion_cutover.get("collector_authority"),
        "cutover_ledger_ready": promotion_cutover.get("cutover_ledger_ready")
    })));
    if !promotion_cutover_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_promotion_cutover_failed", Some("build-collector-authority-promotion-cutover-ledger".to_string()), "Self-test collector authority promotion cutover ledger should report ready only as a non-mutating ledger result."));
    }

    let mut production_freeze_payload = promotion_cutover_payload.clone();
    if let Some(obj) = production_freeze_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE"));
        obj.insert("collector_authority_promotion_cutover_ledger".to_string(), json!(promotion_cutover.clone()));
        obj.insert("maintenance_window".to_string(), json!("2026-05-20T23:00:00+08:00/PT30M"));
        obj.insert("operator_acknowledged".to_string(), json!(true));
        obj.insert("rollback_path".to_string(), json!("python_fallback_revert"));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_production_freeze_gate_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_production_freeze_gate".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_mode".to_string(), json!("freeze_only"));
            rc.insert("collector_authority_production_freeze_require_cutover_ledger".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_rollback_path".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_maintenance_window".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_require_operator_ack".to_string(), json!(true));
            rc.insert("collector_authority_production_freeze_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (production_freeze, production_freeze_errors, _production_freeze_warnings) = build_collector_authority_production_freeze_gate_payload(&production_freeze_payload);
    let production_freeze_ok = production_freeze_errors.is_empty()
        && production_freeze.get("status").and_then(Value::as_str) == Some("collector_authority_production_freeze_gate_ready")
        && production_freeze.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && production_freeze.get("collector_authority_production_switch_executed").and_then(Value::as_bool) == Some(false)
        && production_freeze.get("python_backend_removable").and_then(Value::as_bool) == Some(false);
    checks.push(check("collector_authority_production_freeze_gate", production_freeze_ok, json!({
        "status": production_freeze.get("status"),
        "collector_authority": production_freeze.get("collector_authority"),
        "production_freeze_ready": production_freeze.get("production_freeze_ready")
    })));
    if !production_freeze_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_production_freeze_failed", Some("build-collector-authority-production-freeze-gate".to_string()), "Self-test production freeze gate should report ready only as a non-mutating pre-production gate."));
    }

    let mut production_switch_payload = production_freeze_payload.clone();
    if let Some(obj) = production_switch_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT"));
        obj.insert("collector_authority_production_freeze_gate".to_string(), json!(production_freeze.clone()));
        obj.insert("maintenance_window".to_string(), json!("2026-05-20T23:00:00+08:00/PT30M"));
        obj.insert("operator_acknowledged".to_string(), json!(true));
        obj.insert("rollback_path".to_string(), json!("python_fallback_revert"));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("collector_authority_production_switch_contract_pilot".to_string(), json!(true));
            rc.insert("allow_collector_authority_production_switch_contract".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_mode".to_string(), json!("contract_only"));
            rc.insert("collector_authority_production_switch_require_freeze_gate".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_python_fallback".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_manual_confirmation".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_no_cleanup_apply".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_rollback_path".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_maintenance_window".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_require_operator_ack".to_string(), json!(true));
            rc.insert("collector_authority_production_switch_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (production_switch, production_switch_errors, _production_switch_warnings) = build_collector_authority_production_switch_contract_payload(&production_switch_payload);
    let production_switch_ok = production_switch_errors.is_empty()
        && production_switch.get("status").and_then(Value::as_str) == Some("collector_authority_production_switch_contract_ready")
        && production_switch.get("production_collector_authority_switched").and_then(Value::as_bool) == Some(false)
        && production_switch.get("collector_authority_production_switch_executed").and_then(Value::as_bool) == Some(false)
        && production_switch.get("python_backend_removable").and_then(Value::as_bool) == Some(false)
        && production_switch.get("python_backend_required").and_then(Value::as_bool) == Some(true);
    checks.push(check("collector_authority_production_switch_contract", production_switch_ok, json!({
        "status": production_switch.get("status"),
        "collector_authority": production_switch.get("collector_authority"),
        "production_switch_contract_ready": production_switch.get("production_switch_contract_ready")
    })));
    if !production_switch_ok {
        errors.push(Diagnostic::error("self_test_collector_authority_production_switch_failed", Some("build-collector-authority-production-switch-contract".to_string()), "Self-test production switch contract should report ready without switching authority or removing Python."));
    }

    let mut api_handoff_payload = production_switch_payload.clone();
    if let Some(obj) = api_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN"));
        obj.insert("collector_authority_production_switch_contract".to_string(), json!(production_switch.clone()));
        obj.insert("webui_ux_unchanged".to_string(), json!(true));
        obj.insert("webui_static_assets_unchanged".to_string(), json!(true));
        obj.insert("api_route_parity".to_string(), json!(true));
        obj.insert("api_route_count".to_string(), json!(42));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_backend_api_handoff_plan_pilot".to_string(), json!(true));
            rc.insert("allow_rust_backend_api_handoff_plan".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_mode".to_string(), json!("plan_only"));
            rc.insert("rust_backend_api_handoff_require_production_switch_contract".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_require_python_backend_fallback".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_require_webui_compatibility".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_require_route_parity".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_backend_api_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (api_handoff, api_handoff_errors, _api_handoff_warnings) = build_rust_backend_api_handoff_plan_payload(&api_handoff_payload);
    let api_handoff_ok = api_handoff_errors.is_empty()
        && api_handoff.get("status").and_then(Value::as_str) == Some("rust_backend_api_handoff_plan_ready")
        && api_handoff.get("rust_backend_api_handoff_ready").and_then(Value::as_bool) == Some(true)
        && api_handoff.get("python_backend_removed").and_then(Value::as_bool) == Some(false)
        && api_handoff.get("webui_ux_unchanged").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_backend_api_handoff_plan", api_handoff_ok, json!({
        "status": api_handoff.get("status"),
        "webui_ux_unchanged": api_handoff.get("webui_ux_unchanged"),
        "rust_backend_api_handoff_ready": api_handoff.get("rust_backend_api_handoff_ready")
    })));
    if !api_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_backend_api_handoff_failed", Some("build-rust-backend-api-handoff-plan".to_string()), "Self-test Rust backend API handoff plan should report ready without removing Python or changing WebUI/UX."));
    }

    let mut scheduler_handoff_payload = api_handoff_payload.clone();
    if let Some(obj) = scheduler_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_BACKEND_SCHEDULER_RUN_CYCLE_HANDOFF_PLAN"));
        obj.insert("rust_backend_api_handoff_plan".to_string(), json!(api_handoff.clone()));
        obj.insert("scheduler_manifest_ready".to_string(), json!(true));
        obj.insert("scheduler_interval_seconds".to_string(), json!(30));
        obj.insert("run_cycle_shadow_ready".to_string(), json!(true));
        obj.insert("run_cycle_shadow_count".to_string(), json!(3));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_backend_scheduler_handoff_plan_pilot".to_string(), json!(true));
            rc.insert("allow_rust_backend_scheduler_handoff_plan".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_mode".to_string(), json!("plan_only"));
            rc.insert("rust_backend_scheduler_handoff_require_api_handoff".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_require_run_cycle_shadow".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_require_scheduler_parity".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_backend_scheduler_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (scheduler_handoff, scheduler_handoff_errors, _scheduler_handoff_warnings) = build_rust_backend_scheduler_handoff_plan_payload(&scheduler_handoff_payload);
    let scheduler_handoff_ok = scheduler_handoff_errors.is_empty()
        && scheduler_handoff.get("status").and_then(Value::as_str) == Some("rust_backend_scheduler_handoff_plan_ready")
        && scheduler_handoff.get("rust_backend_scheduler_handoff_ready").and_then(Value::as_bool) == Some(true)
        && scheduler_handoff.get("rust_scheduler_authoritative").and_then(Value::as_bool) == Some(false)
        && scheduler_handoff.get("rust_run_cycle_authoritative").and_then(Value::as_bool) == Some(false);
    checks.push(check("rust_backend_scheduler_handoff_plan", scheduler_handoff_ok, json!({
        "status": scheduler_handoff.get("status"),
        "rust_backend_scheduler_handoff_ready": scheduler_handoff.get("rust_backend_scheduler_handoff_ready"),
        "rust_scheduler_authoritative": scheduler_handoff.get("rust_scheduler_authoritative")
    })));
    if !scheduler_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_backend_scheduler_handoff_failed", Some("build-rust-backend-scheduler-handoff-plan".to_string()), "Self-test Rust scheduler/run_cycle handoff plan should report ready without switching scheduler/run_cycle authority."));
    }

    let mut run_cycle_orchestrator_payload = scheduler_handoff_payload.clone();
    if let Some(obj) = run_cycle_orchestrator_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT"));
        obj.insert("rust_backend_scheduler_handoff_plan".to_string(), json!(scheduler_handoff.clone()));
        obj.insert("run_cycle_orchestrator_manifest_ready".to_string(), json!(true));
        obj.insert("run_cycle_shadow_ready".to_string(), json!(true));
        obj.insert("run_cycle_shadow_count".to_string(), json!(3));
        obj.insert("config_state_shadow_ready".to_string(), json!(true));
        obj.insert("config_state_shadow_count".to_string(), json!(3));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_run_cycle_orchestrator_handoff_contract_pilot".to_string(), json!(true));
            rc.insert("allow_rust_run_cycle_orchestrator_handoff_contract".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_mode".to_string(), json!("contract_only"));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_scheduler_handoff".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_config_state_shadow".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (run_cycle_orchestrator, run_cycle_orchestrator_errors, _run_cycle_orchestrator_warnings) = build_rust_run_cycle_orchestrator_handoff_contract_payload(&run_cycle_orchestrator_payload);
    let run_cycle_orchestrator_ok = run_cycle_orchestrator_errors.is_empty()
        && run_cycle_orchestrator.get("status").and_then(Value::as_str) == Some("rust_run_cycle_orchestrator_handoff_contract_ready")
        && run_cycle_orchestrator.get("rust_run_cycle_orchestrator_handoff_ready").and_then(Value::as_bool) == Some(true)
        && run_cycle_orchestrator.get("rust_run_cycle_authoritative").and_then(Value::as_bool) == Some(false)
        && run_cycle_orchestrator.get("python_run_cycle_authoritative").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_run_cycle_orchestrator_handoff_contract", run_cycle_orchestrator_ok, json!({
        "status": run_cycle_orchestrator.get("status"),
        "rust_run_cycle_orchestrator_handoff_ready": run_cycle_orchestrator.get("rust_run_cycle_orchestrator_handoff_ready"),
        "rust_run_cycle_authoritative": run_cycle_orchestrator.get("rust_run_cycle_authoritative")
    })));
    if !run_cycle_orchestrator_ok {
        errors.push(Diagnostic::error("self_test_rust_run_cycle_orchestrator_handoff_failed", Some("build-rust-run-cycle-orchestrator-handoff-contract".to_string()), "Self-test Rust run_cycle orchestrator handoff contract should report ready without switching run_cycle authority."));
    }

    let mut config_state_handoff_payload = run_cycle_orchestrator_payload.clone();
    if let Some(obj) = config_state_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_CONFIG_STATE_AUTHORITY_HANDOFF_CONTRACT"));
        obj.insert("rust_run_cycle_orchestrator_handoff_contract".to_string(), json!(run_cycle_orchestrator.clone()));
        obj.insert("config_state_shadow_ready".to_string(), json!(true));
        obj.insert("config_state_shadow_count".to_string(), json!(3));
        obj.insert("atomic_writer_shadow_ready".to_string(), json!(true));
        obj.insert("atomic_writer_shadow_count".to_string(), json!(3));
        obj.insert("transaction_journal_shadow_ready".to_string(), json!(true));
        obj.insert("transaction_journal_shadow_count".to_string(), json!(3));
        obj.insert("audit_shadow_ready".to_string(), json!(true));
        obj.insert("audit_shadow_count".to_string(), json!(3));
        obj.insert("rollback_manifest_shadow_ready".to_string(), json!(true));
        obj.insert("rollback_manifest_shadow_count".to_string(), json!(3));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_config_state_authority_handoff_contract_pilot".to_string(), json!(true));
            rc.insert("allow_rust_config_state_authority_handoff_contract".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_mode".to_string(), json!("contract_only"));
            rc.insert("rust_config_state_authority_handoff_require_run_cycle_orchestrator".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_config_state_shadow".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_atomic_writer_shadow".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_transaction_journal_shadow".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_audit_shadow".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_rollback_shadow".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_config_state_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (config_state_handoff, config_state_handoff_errors, _config_state_handoff_warnings) = build_rust_config_state_authority_handoff_contract_payload(&config_state_handoff_payload);
    let config_state_handoff_ok = config_state_handoff_errors.is_empty()
        && config_state_handoff.get("status").and_then(Value::as_str) == Some("rust_config_state_authority_handoff_contract_ready")
        && config_state_handoff.get("rust_config_state_authority_handoff_ready").and_then(Value::as_bool) == Some(true)
        && config_state_handoff.get("rust_config_state_authoritative").and_then(Value::as_bool) == Some(false)
        && config_state_handoff.get("python_config_state_authoritative").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_config_state_authority_handoff_contract", config_state_handoff_ok, json!({
        "status": config_state_handoff.get("status"),
        "rust_config_state_authority_handoff_ready": config_state_handoff.get("rust_config_state_authority_handoff_ready"),
        "rust_config_state_authoritative": config_state_handoff.get("rust_config_state_authoritative")
    })));
    if !config_state_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_config_state_authority_handoff_failed", Some("build-rust-config-state-authority-handoff-contract".to_string()), "Self-test Rust config/state authority handoff contract should report ready without switching config/state authority."));
    }

    let mut live_collector_handoff_payload = config_state_handoff_payload.clone();
    if let Some(obj) = live_collector_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_LIVE_COLLECTOR_AUTHORITY_HANDOFF_CONTRACT"));
        obj.insert("rust_config_state_authority_handoff_contract".to_string(), json!(config_state_handoff.clone()));
        obj.insert("live_collector_shadow_ready".to_string(), json!(true));
        obj.insert("live_collector_shadow_count".to_string(), json!(3));
        obj.insert("routeros_live_adapter_shadow_ready".to_string(), json!(true));
        obj.insert("routeros_live_adapter_shadow_count".to_string(), json!(3));
        obj.insert("collector_parity_verdict".to_string(), json!("parity_pass"));
        obj.insert("collector_parity_score".to_string(), json!(100.0));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_live_collector_authority_handoff_contract_pilot".to_string(), json!(true));
            rc.insert("allow_rust_live_collector_authority_handoff_contract".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_mode".to_string(), json!("contract_only"));
            rc.insert("rust_live_collector_authority_handoff_require_config_state_authority".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_live_collector_shadow".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_routeros_adapter_shadow".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_collector_parity".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_live_collector_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (live_collector_handoff, live_collector_handoff_errors, _live_collector_handoff_warnings) = build_rust_live_collector_authority_handoff_contract_payload(&live_collector_handoff_payload);
    let live_collector_handoff_ok = live_collector_handoff_errors.is_empty()
        && live_collector_handoff.get("status").and_then(Value::as_str) == Some("rust_live_collector_authority_handoff_contract_ready")
        && live_collector_handoff.get("rust_live_collector_authority_handoff_ready").and_then(Value::as_bool) == Some(true)
        && live_collector_handoff.get("rust_live_collector_authoritative").and_then(Value::as_bool) == Some(false)
        && live_collector_handoff.get("python_live_collector_authoritative").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_live_collector_authority_handoff_contract", live_collector_handoff_ok, json!({
        "status": live_collector_handoff.get("status"),
        "rust_live_collector_authority_handoff_ready": live_collector_handoff.get("rust_live_collector_authority_handoff_ready"),
        "rust_live_collector_authoritative": live_collector_handoff.get("rust_live_collector_authoritative")
    })));
    if !live_collector_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_live_collector_authority_handoff_failed", Some("build-rust-live-collector-authority-handoff-contract".to_string()), "Self-test Rust live collector authority handoff contract should report ready without switching live collector authority."));
    }

    let mut circuit_builder_handoff_payload = live_collector_handoff_payload.clone();
    if let Some(obj) = circuit_builder_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT"));
        obj.insert("rust_live_collector_authority_handoff_contract".to_string(), json!(live_collector_handoff.clone()));
        obj.insert("circuit_builder_shadow_ready".to_string(), json!(true));
        obj.insert("circuit_builder_shadow_count".to_string(), json!(3));
        obj.insert("shaped_devices_render_parity_ready".to_string(), json!(true));
        obj.insert("shaped_devices_render_parity_score".to_string(), json!(100.0));
        obj.insert("parent_node_integrity_ready".to_string(), json!(true));
        obj.insert("parent_node_error_count".to_string(), json!(0));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_circuit_builder_authority_handoff_contract_pilot".to_string(), json!(true));
            rc.insert("allow_rust_circuit_builder_authority_handoff_contract".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_mode".to_string(), json!("contract_only"));
            rc.insert("rust_circuit_builder_authority_handoff_require_live_collector_authority".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_circuit_shadow".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_shaped_devices_parity".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_parent_integrity".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_circuit_builder_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (circuit_builder_handoff, circuit_builder_handoff_errors, _circuit_builder_handoff_warnings) = build_rust_circuit_builder_authority_handoff_contract_payload(&circuit_builder_handoff_payload);
    let circuit_builder_handoff_ok = circuit_builder_handoff_errors.is_empty()
        && circuit_builder_handoff.get("status").and_then(Value::as_str) == Some("rust_circuit_builder_authority_handoff_contract_ready")
        && circuit_builder_handoff.get("rust_circuit_builder_authority_handoff_ready").and_then(Value::as_bool) == Some(true)
        && circuit_builder_handoff.get("rust_circuit_builder_authoritative").and_then(Value::as_bool) == Some(false)
        && circuit_builder_handoff.get("python_circuit_builder_authoritative").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_circuit_builder_authority_handoff_contract", circuit_builder_handoff_ok, json!({
        "status": circuit_builder_handoff.get("status"),
        "rust_circuit_builder_authority_handoff_ready": circuit_builder_handoff.get("rust_circuit_builder_authority_handoff_ready"),
        "rust_circuit_builder_authoritative": circuit_builder_handoff.get("rust_circuit_builder_authoritative")
    })));
    if !circuit_builder_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_circuit_builder_authority_handoff_failed", Some("build-rust-circuit-builder-authority-handoff-contract".to_string()), "Self-test Rust circuit builder authority handoff contract should report ready without switching circuit builder authority."));
    }

    let mut sync_engine_handoff_payload = circuit_builder_handoff_payload.clone();
    if let Some(obj) = sync_engine_handoff_payload.as_object_mut() {
        obj.insert("confirmation".to_string(), json!("CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT"));
        obj.insert("rust_circuit_builder_authority_handoff_contract".to_string(), json!(circuit_builder_handoff.clone()));
        obj.insert("sync_plan_shadow_ready".to_string(), json!(true));
        obj.insert("sync_plan_shadow_count".to_string(), json!(3));
        obj.insert("sync_diff_parity_ready".to_string(), json!(true));
        obj.insert("sync_diff_parity_score".to_string(), json!(100.0));
        obj.insert("apply_manifest_preview_ready".to_string(), json!(true));
        obj.insert("apply_manifest_preview_blocker_count".to_string(), json!(0));
        obj.insert("cleanup_safety_ready".to_string(), json!(true));
        obj.insert("cleanup_candidate_count".to_string(), json!(0));
        if let Some(rc) = obj.get_mut("rust_core").and_then(Value::as_object_mut) {
            rc.insert("rust_sync_engine_authority_handoff_contract_pilot".to_string(), json!(true));
            rc.insert("allow_rust_sync_engine_authority_handoff_contract".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_mode".to_string(), json!("contract_only"));
            rc.insert("rust_sync_engine_authority_handoff_require_circuit_builder_authority".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_python_fallback".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_manual_confirmation".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_sync_plan_shadow".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_diff_parity".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_apply_manifest_preview".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_cleanup_safety".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_require_no_side_effects".to_string(), json!(true));
            rc.insert("rust_sync_engine_authority_handoff_max_shadow_age_seconds".to_string(), json!(900));
        }
    }
    let (sync_engine_handoff, sync_engine_handoff_errors, _sync_engine_handoff_warnings) = build_rust_sync_engine_authority_handoff_contract_payload(&sync_engine_handoff_payload);
    let sync_engine_handoff_ok = sync_engine_handoff_errors.is_empty()
        && sync_engine_handoff.get("status").and_then(Value::as_str) == Some("rust_sync_engine_authority_handoff_contract_ready")
        && sync_engine_handoff.get("rust_sync_engine_authority_handoff_ready").and_then(Value::as_bool) == Some(true)
        && sync_engine_handoff.get("rust_sync_engine_authoritative").and_then(Value::as_bool) == Some(false)
        && sync_engine_handoff.get("python_sync_engine_authoritative").and_then(Value::as_bool) == Some(true);
    checks.push(check("rust_sync_engine_authority_handoff_contract", sync_engine_handoff_ok, json!({
        "status": sync_engine_handoff.get("status"),
        "rust_sync_engine_authority_handoff_ready": sync_engine_handoff.get("rust_sync_engine_authority_handoff_ready"),
        "rust_sync_engine_authoritative": sync_engine_handoff.get("rust_sync_engine_authoritative")
    })));
    if !sync_engine_handoff_ok {
        errors.push(Diagnostic::error("self_test_rust_sync_engine_authority_handoff_failed", Some("build-rust-sync-engine-authority-handoff-contract".to_string()), "Self-test Rust sync engine authority handoff contract should report ready without switching sync engine authority."));
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
        assert!(ops.contains(&OP_RUN_ROUTEROS_READ_PILOT));
        assert!(ops.contains(&OP_BUILD_ROUTEROS_API_SENTENCE));
        assert!(ops.contains(&OP_BUILD_ROUTEROS_AUTH_PLAN));
        assert!(ops.contains(&OP_BUILD_RUN_CYCLE_RUST_SHADOW_REPORT));
        assert!(ops.contains(&OP_BUILD_COLLECTOR_AUTHORITY_SWITCH_REHEARSAL));
        assert!(ops.contains(&OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_READINESS));
        assert!(ops.contains(&OP_BUILD_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL));
        assert!(ops.contains(&OP_BUILD_COLLECTOR_CIRCUIT_BUNDLE));
        assert!(ops.contains(&OP_COMPARE_COLLECTOR_BUNDLE_PARITY));
        assert!(ops.contains(&OP_EVALUATE_AUTHORITY_READINESS));
        assert!(ops.contains(&OP_SELF_TEST));
    }
}
