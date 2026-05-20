use crate::protocol::{Diagnostic, Severity};
use serde_json::{json, Value};

fn bool_at(root: &Value, path: &[&str], default: bool) -> bool {
    let mut cur = root;
    for key in path {
        match cur.get(*key) {
            Some(v) => cur = v,
            None => return default,
        }
    }
    cur.as_bool().unwrap_or(default)
}

fn str_at(root: &Value, path: &[&str], default: &str) -> String {
    let mut cur = root;
    for key in path {
        match cur.get(*key) {
            Some(v) => cur = v,
            None => return default.to_string(),
        }
    }
    cur.as_str().unwrap_or(default).to_string()
}

fn arr_strings(root: &Value, path: &[&str]) -> Vec<String> {
    let mut cur = root;
    for key in path {
        match cur.get(*key) {
            Some(v) => cur = v,
            None => return Vec::new(),
        }
    }
    cur.as_array()
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default()
}

fn diag(code: &str, severity: Severity, path: &str, message: &str) -> Diagnostic {
    Diagnostic {
        code: code.to_string(),
        severity,
        path: Some(path.to_string()),
        message: message.to_string(),
        value: None,
        safe_for_cleanup: None,
    }
}

fn has_all(ops: &[String], required: &[&str]) -> Vec<String> {
    required.iter().filter(|op| !ops.iter().any(|have| have == **op)).map(|s| s.to_string()).collect()
}

pub fn evaluate_full_rust_readiness_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let config = payload.get("config").unwrap_or(&Value::Null);
    let status = payload.get("rust_core_status").unwrap_or(&Value::Null);
    let self_test = payload.get("self_test").unwrap_or(&Value::Null);
    let authority = payload.get("authority_readiness").unwrap_or(&Value::Null);
    let rc = config.get("rust_core").unwrap_or(&Value::Null);
    let operations = arr_strings(self_test, &["result", "operations"]);

    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let mut blockers = Vec::new();
    let mut implemented = Vec::new();
    let mut remaining = Vec::new();
    let mut next_steps = Vec::new();

    let enabled = bool_at(rc, &["enabled"], true);
    let transport_ok = status.get("available").and_then(Value::as_bool).unwrap_or(true)
        && status.get("ok").and_then(Value::as_bool).unwrap_or(true);
    let self_test_ok = self_test.get("ok").and_then(Value::as_bool).unwrap_or(true)
        && str_at(self_test, &["result", "status"], "ok") == "ok";
    let authority_verdict = str_at(authority, &["result", "verdict"], "shadow_safe");

    let required = [
        "validate-files",
        "validate-collector-output",
        "diff-files",
        "evaluate-policy",
        "normalize-circuits",
        "evaluate-sync-plan",
        "build-apply-manifest",
        "execute-apply-transaction",
        "build-transaction-journal",
        "append-transaction-journal",
        "read-transaction-journal",
        "build-rollback-from-journal",
        "execute-rollback",
        "evaluate-authority-readiness",
        "self-test",
    ];
    let missing_required = has_all(&operations, &required);

    implemented.push(json!({"component":"rust_protocol_daemon","status": if transport_ok {"ready"} else {"not_ready"}, "rust_owned": true}));
    implemented.push(json!({"component":"validation_diff_core","status": if missing_required.is_empty() {"ready"} else {"partial"}, "rust_owned": true}));
    implemented.push(json!({"component":"collector_trust_contract","status":"ready", "rust_owned": true, "note":"Rust validates collector output, but does not collect RouterOS data yet."}));
    implemented.push(json!({"component":"policy_engine","status":"shadow", "rust_owned": "partial", "note":"Rust policy remains a shadow evaluator; Python policy is still authoritative by default."}));
    implemented.push(json!({"component":"circuit_normalizer","status":"shadow", "rust_owned": "partial", "note":"Rust normalizes circuit rows from proposed output; Python collectors/builders still create authoritative rows."}));
    implemented.push(json!({"component":"sync_plan_apply_transaction_journal_rollback","status":"gated_ready", "rust_owned": true, "note":"Rust can plan/rehearse/optionally write files and rollback only behind explicit authority flags."}));

    remaining.push(json!({"component":"webui_auth_routes_templates", "owner":"python", "reason":"Flask/Jinja UI remains the operator surface."}));
    remaining.push(json!({"component":"scheduler_runner", "owner":"python", "reason":"Python scheduler still starts run_cycle and manual sync jobs."}));
    remaining.push(json!({"component":"run_cycle_orchestration", "owner":"python", "reason":"Python still orchestrates collection, cleanup, write/apply decisions by default."}));
    remaining.push(json!({"component":"routeros_api_collectors", "owner":"python", "reason":"Python routeros-api collectors still read PPPoE/DHCP/Hotspot data."}));
    remaining.push(json!({"component":"libreqos_external_apply", "owner":"python", "reason":"Rust transaction executor does not invoke LibreQoS.py in this release."}));
    remaining.push(json!({"component":"service_monitor_docs_notifications", "owner":"python", "reason":"Operations visibility and UI services remain Python."}));

    if !enabled {
        errors.push(diag("rust_core_disabled", Severity::Error, "rust_core.enabled", "Rust core is disabled."));
        blockers.push(json!({"code":"rust_core_disabled","message":"Enable Rust core before authority pilots."}));
    }
    if !transport_ok {
        errors.push(diag("rust_transport_not_ready", Severity::Error, "rust_core", "Rust core transport is not healthy."));
        blockers.push(json!({"code":"rust_transport_not_ready","message":"Rust CLI/daemon is not healthy."}));
    }
    if !self_test_ok {
        errors.push(diag("rust_self_test_not_ready", Severity::Error, "rust_core.self_test", "Rust core self-test is not passing."));
        blockers.push(json!({"code":"rust_self_test_not_ready","message":"Self-test must pass before authority pilots."}));
    }
    if !missing_required.is_empty() {
        errors.push(Diagnostic::error("rust_required_operations_missing", Some("operations".to_string()), "Required Rust operations are missing.").with_value(json!(missing_required)));
        blockers.push(json!({"code":"rust_required_operations_missing","message":"One or more required Rust operations are missing."}));
    }

    if authority_verdict == "not_ready" {
        warnings.push(diag("authority_readiness_not_ready", Severity::Warning, "authority_readiness", "Authority readiness reports not_ready; keep Rust in shadow mode."));
    }

    next_steps.push(json!({"step":1,"title":"Keep Python WebUI and scheduler authoritative","action":"Do not call this full Rust backend yet; continue hybrid authority-pilot mode.","risk":"low"}));
    next_steps.push(json!({"step":2,"title":"Pilot sync-plan enforcement","action":"Enable enforce_sync_plan only after authority readiness is clean.","risk":"medium"}));
    next_steps.push(json!({"step":3,"title":"Pilot transaction journal persistence","action":"Enable append_transaction_journal + allow_transaction_journal_writes before Rust file writes.","risk":"medium"}));
    next_steps.push(json!({"step":4,"title":"Pilot Rust file writes on lab/dry-run-matched systems","action":"Enable execute_apply_manifest + allow_rust_file_writes only after several clean cycles.","risk":"high"}));
    next_steps.push(json!({"step":5,"title":"Migrate collector normalization before RouterOS API rewrite","action":"Move PPPoE/DHCP/Hotspot row-building logic to Rust before replacing RouterOS API transport.","risk":"high"}));

    let authority_flags = bool_at(rc, &["enforce_sync_plan"], false)
        || bool_at(rc, &["execute_apply_manifest"], false)
        || bool_at(rc, &["allow_rust_file_writes"], false)
        || bool_at(rc, &["append_transaction_journal"], false)
        || bool_at(rc, &["allow_transaction_journal_writes"], false)
        || bool_at(rc, &["execute_rollback"], false)
        || bool_at(rc, &["allow_rust_rollback_file_writes"], false);

    let maturity = if !blockers.is_empty() {
        "rust_core_not_ready"
    } else if authority_flags {
        "authority_pilot_active"
    } else {
        "hybrid_shadow_ready"
    };
    let full_backend_ready = false;
    let backend_model = if authority_flags { "hybrid_rust_authority_pilot" } else { "hybrid_python_authoritative_rust_safety_core" };

    let result = json!({
        "mode": "full_rust_readiness",
        "full_backend_ready": full_backend_ready,
        "backend_model": backend_model,
        "maturity": maturity,
        "verdict": if full_backend_ready {"full_rust_backend_ready"} else {"not_full_rust_backend_yet"},
        "summary": "LQoSync is currently a hybrid system: Python remains the WebUI/orchestrator/collector authority by default, while Rust provides safety, planning, transaction, journal, rollback, and optional authority gates.",
        "rust_operations_count": operations.len(),
        "required_operations_missing": missing_required,
        "implemented_rust_capabilities": implemented,
        "remaining_python_authoritative_components": remaining,
        "blockers": blockers,
        "next_steps": next_steps,
        "authority_readiness_verdict": authority_verdict,
    });
    (result, errors, warnings)
}

fn stage(id: u64, name: &str, status: &str, description: &str, config_delta: Value, gate: Value) -> Value {
    json!({"stage": id, "name": name, "status": status, "description": description, "config_delta": config_delta, "gate": gate})
}

pub fn build_authority_pilot_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let config = payload.get("config").unwrap_or(&Value::Null);
    let readiness = payload.get("authority_readiness").unwrap_or(&Value::Null);
    let full = payload.get("full_backend_readiness").unwrap_or(&Value::Null);
    let rc = config.get("rust_core").unwrap_or(&Value::Null);
    let readiness_result = readiness.get("result").unwrap_or(readiness);
    let readiness_verdict = str_at(readiness_result, &["verdict"], "shadow_safe");
    let full_backend_ready = full.get("result").and_then(|v| v.get("full_backend_ready")).and_then(Value::as_bool).unwrap_or(false);

    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let mut stages = Vec::new();

    let transport_ready = readiness_verdict != "not_ready";
    let enforce_enabled = bool_at(rc, &["enforce_sync_plan"], false) || str_at(rc, &["authority_mode"], "shadow") == "enforce_blockers";
    let journal_enabled = bool_at(rc, &["append_transaction_journal"], false) && bool_at(rc, &["allow_transaction_journal_writes"], false);
    let file_write_enabled = bool_at(rc, &["execute_apply_manifest"], false) && bool_at(rc, &["allow_rust_file_writes"], false);
    let rollback_enabled = bool_at(rc, &["execute_rollback"], false) && bool_at(rc, &["allow_rust_rollback_file_writes"], false) && str_at(rc, &["rollback_authority"], "preview") == "execute_file_restores";

    stages.push(stage(0, "Shadow baseline", "current_or_complete", "Rust validates, plans, journals, and rehearses while Python remains authoritative.", json!({"authority_mode":"shadow"}), json!({"required":"self-test OK"})));
    stages.push(stage(1, "Daemon and self-test", if transport_ready {"ready"} else {"blocked"}, "Prefer daemon transport and require self-test/capability audit before authority flags.", json!({"prefer_daemon":true,"self_test_on_status":false}), json!({"readiness_verdict": readiness_verdict})));
    stages.push(stage(2, "Sync-plan enforcement", if !transport_ready {"blocked"} else if enforce_enabled {"active"} else {"available"}, "Allow Rust sync-plan blockers to stop non-dry-run writes before file mutation.", json!({"enforce_sync_plan":true,"fail_closed_when_enforced":true,"authority_mode":"enforce_blockers"}), json!({"requires":"several clean dry-runs and no Rust blockers"})));
    stages.push(stage(3, "Transaction journal persistence", if !transport_ready {"blocked"} else if journal_enabled {"active"} else {"available"}, "Persist transaction journal JSONL before enabling Rust file writes.", json!({"append_transaction_journal":true,"allow_transaction_journal_writes":true,"include_rehearsal_journal_entries":false,"allow_dry_run_journal_entries":false}), json!({"path":"/opt/LQoSync/logs/transaction_journal.jsonl"})));
    stages.push(stage(4, "Rust file-write pilot", if !journal_enabled {"blocked_until_journal_enabled"} else if file_write_enabled {"active"} else {"available_after_journal"}, "Allow Rust to atomically write ShapedDevices.csv/network.json only after journal persistence is enabled.", json!({"execute_apply_manifest":true,"allow_rust_file_writes":true,"transaction_authority":"execute_file_writes"}), json!({"requires":"journal persistence + backup verification + operator approval"})));
    stages.push(stage(5, "Rollback execution pilot", if !file_write_enabled {"blocked_until_file_write_pilot"} else if rollback_enabled {"active"} else {"available_after_file_write_pilot"}, "Enable explicit confirmed rollback restores only after successful Rust file-write pilot cycles.", json!({"execute_rollback":true,"allow_rust_rollback_file_writes":true,"rollback_authority":"execute_file_restores"}), json!({"requires":"CONFIRM_ROLLBACK per request"})));
    stages.push(stage(6, "Collector/circuit migration", "future_work", "Move PPPoE/DHCP/Hotspot row-building into Rust before any RouterOS API transport rewrite.", json!({}), json!({"requires":"new Rust collector normalization parity tests"})));

    if !transport_ready {
        errors.push(Diagnostic::error("authority_pilot_blocked", Some("authority_readiness".to_string()), "Authority pilot is blocked until Rust authority readiness is clean."));
    }
    if file_write_enabled && !journal_enabled {
        warnings.push(diag("file_write_without_journal_pilot", Severity::Warning, "rust_core.append_transaction_journal", "Rust file-write pilot should not be active without transaction journal persistence."));
    }
    if full_backend_ready {
        warnings.push(diag("unexpected_full_backend_ready", Severity::Warning, "full_backend_readiness", "Full backend readiness unexpectedly reports true; review remaining Python ownership before changing architecture."));
    }

    let recommended_next_stage = stages.iter()
        .filter(|s| matches!(s.get("status").and_then(Value::as_str), Some("available") | Some("available_after_journal") | Some("available_after_file_write_pilot")))
        .next()
        .cloned()
        .unwrap_or_else(|| json!({"stage":0,"name":"No safe next stage","status":"none"}));

    let result = json!({
        "mode": "authority_pilot_plan",
        "full_backend_ready": false,
        "pilot_only": true,
        "readiness_verdict": readiness_verdict,
        "recommended_next_stage": recommended_next_stage,
        "stages": stages,
        "guardrails": [
            "Keep Python authoritative until multiple clean Rust authority pilot cycles pass.",
            "Enable journal persistence before Rust file writes.",
            "Never enable rollback execution without explicit confirmation per request.",
            "Do not treat this as a full Rust backend until RouterOS collection and run_cycle orchestration are migrated."
        ],
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reports_not_full_rust_backend_yet() {
        let payload = json!({
            "config": {"rust_core": {"enabled": true}},
            "rust_core_status": {"available": true, "ok": true},
            "self_test": {"ok": true, "result": {"status": "ok", "operations": [
                "validate-files", "validate-collector-output", "diff-files", "evaluate-policy", "normalize-circuits", "evaluate-sync-plan", "build-apply-manifest", "execute-apply-transaction", "build-transaction-journal", "append-transaction-journal", "read-transaction-journal", "build-rollback-from-journal", "execute-rollback", "evaluate-authority-readiness", "self-test"
            ]}},
            "authority_readiness": {"result": {"verdict": "shadow_safe"}}
        });
        let (result, errors, _warnings) = evaluate_full_rust_readiness_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("full_backend_ready").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("not_full_rust_backend_yet"));
    }

    #[test]
    fn pilot_plan_has_ordered_stages() {
        let payload = json!({
            "config": {"rust_core": {"enabled": true}},
            "authority_readiness": {"result": {"verdict": "shadow_safe"}},
            "full_backend_readiness": {"result": {"full_backend_ready": false}}
        });
        let (result, errors, _warnings) = build_authority_pilot_plan_payload(&payload);
        assert!(errors.is_empty());
        assert!(result.get("stages").and_then(Value::as_array).unwrap().len() >= 6);
    }
}
