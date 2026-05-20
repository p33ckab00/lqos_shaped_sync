use crate::protocol::{Diagnostic, Severity};
use serde_json::{json, Value};

fn bool_at<'a>(root: &'a Value, path: &[&str], default: bool) -> bool {
    let mut current = root;
    for part in path {
        match current.get(*part) {
            Some(next) => current = next,
            None => return default,
        }
    }
    current.as_bool().unwrap_or(default)
}

fn str_at<'a>(root: &'a Value, path: &[&str], default: &'a str) -> &'a str {
    let mut current = root;
    for part in path {
        match current.get(*part) {
            Some(next) => current = next,
            None => return default,
        }
    }
    current.as_str().unwrap_or(default)
}

fn warn(code: &str, path: &str, message: &str) -> Diagnostic {
    Diagnostic {
        code: code.to_string(),
        severity: Severity::Warning,
        path: Some(path.to_string()),
        message: message.to_string(),
        value: None,
        safe_for_cleanup: None,
    }
}

fn err(code: &str, path: &str, message: &str) -> Diagnostic {
    Diagnostic {
        code: code.to_string(),
        severity: Severity::Error,
        path: Some(path.to_string()),
        message: message.to_string(),
        value: None,
        safe_for_cleanup: None,
    }
}

fn check(name: &str, ok: bool, severity: &str, details: Value) -> Value {
    json!({"name": name, "ok": ok, "severity": severity, "details": details})
}

/// Evaluate whether it is safe to enable Rust authority flags.
///
/// This operation is read-only. It does not inspect live files beyond the
/// payload it receives, and it never writes/apply/restores anything. It is meant
/// to be shown before operators enable sync-plan enforcement, Rust file writes,
/// journal persistence, or rollback restoration.
pub fn evaluate_authority_readiness_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let config = payload.get("config").unwrap_or(&Value::Null);
    let rust_core = config.get("rust_core").unwrap_or(&Value::Null);
    let paths = config.get("paths").unwrap_or(&Value::Null);
    let status = payload.get("rust_core_status").unwrap_or(&Value::Null);
    let self_test = payload.get("self_test").unwrap_or(&Value::Null);
    let journal_summary = payload.get("journal_summary").unwrap_or(&Value::Null);

    let enabled = bool_at(rust_core, &["enabled"], true);
    let prefer_daemon = bool_at(rust_core, &["prefer_daemon"], false);
    let enforce_sync_plan = bool_at(rust_core, &["enforce_sync_plan"], false);
    let fail_closed = bool_at(rust_core, &["fail_closed_when_enforced"], true);
    let authority_mode = str_at(rust_core, &["authority_mode"], "shadow");
    let execute_apply_manifest = bool_at(rust_core, &["execute_apply_manifest"], false);
    let allow_file_writes = bool_at(rust_core, &["allow_rust_file_writes"], false);
    let allow_libreqos_apply = bool_at(rust_core, &["allow_rust_libreqos_apply"], false);
    let append_journal = bool_at(rust_core, &["append_transaction_journal"], false);
    let allow_journal_writes = bool_at(rust_core, &["allow_transaction_journal_writes"], false);
    let include_rehearsal_journal = bool_at(rust_core, &["include_rehearsal_journal_entries"], false);
    let allow_dry_run_journal = bool_at(rust_core, &["allow_dry_run_journal_entries"], false);
    let execute_rollback = bool_at(rust_core, &["execute_rollback"], false);
    let allow_rollback_writes = bool_at(rust_core, &["allow_rust_rollback_file_writes"], false);
    let rollback_authority = str_at(rust_core, &["rollback_authority"], "preview");

    let transaction_journal_path = str_at(paths, &["transaction_journal"], "");
    let shaped_path = str_at(paths, &["shaped_devices_csv"], "");
    let network_path = str_at(paths, &["network_json"], "");

    let rust_available = status.get("available").and_then(Value::as_bool).unwrap_or(true);
    let status_ok = status.get("ok").and_then(Value::as_bool).unwrap_or(true);
    let self_test_ok = self_test.get("ok").and_then(Value::as_bool).unwrap_or(true);
    let self_test_status = self_test
        .get("result")
        .and_then(|r| r.get("status"))
        .and_then(Value::as_str)
        .unwrap_or("ok");
    let journal_entries = journal_summary.get("total_count").and_then(Value::as_u64).unwrap_or(0);

    let mut checks: Vec<Value> = Vec::new();
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let mut blockers: Vec<Value> = Vec::new();
    let mut recommendations: Vec<Value> = Vec::new();
    let mut risk_score: i64 = 0;

    checks.push(check("rust_core_enabled", enabled, "required", json!({"enabled": enabled})));
    if !enabled {
        blockers.push(json!({"code":"rust_core_disabled","message":"Rust core is disabled; authority flags must remain off."}));
        errors.push(err("rust_core_disabled", "rust_core.enabled", "Rust core is disabled."));
        risk_score += 40;
    }

    let transport_ok = rust_available && status_ok;
    checks.push(check("transport_available", transport_ok, "required", json!({"available": rust_available, "status_ok": status_ok, "prefer_daemon": prefer_daemon})));
    if !transport_ok {
        blockers.push(json!({"code":"rust_transport_unavailable","message":"Rust core transport is not available or not healthy."}));
        errors.push(err("rust_transport_unavailable", "rust_core", "Rust core transport is not available or not healthy."));
        risk_score += 40;
    }

    let self_test_ready = self_test_ok && self_test_status == "ok";
    checks.push(check("self_test_ok", self_test_ready, "required", json!({"ok": self_test_ok, "status": self_test_status})));
    if !self_test_ready {
        blockers.push(json!({"code":"rust_self_test_failed","message":"Rust core self-test is not passing."}));
        errors.push(err("rust_self_test_failed", "rust_core.self_test", "Rust core self-test is not passing."));
        risk_score += 45;
    }

    let generated_paths_ok = !shaped_path.is_empty() && !network_path.is_empty();
    checks.push(check("generated_file_paths_present", generated_paths_ok, "required", json!({"shaped_devices_csv": shaped_path, "network_json": network_path})));
    if !generated_paths_ok {
        blockers.push(json!({"code":"generated_paths_missing","message":"Generated file paths must be present before Rust file-write authority can be enabled."}));
        errors.push(err("generated_paths_missing", "paths", "Generated file paths are missing."));
        risk_score += 35;
    }

    if enforce_sync_plan || authority_mode == "enforce_blockers" {
        checks.push(check("sync_plan_enforcement_fail_closed", fail_closed, "required", json!({"fail_closed_when_enforced": fail_closed, "authority_mode": authority_mode})));
        if !fail_closed {
            warnings.push(warn("sync_plan_not_fail_closed", "rust_core.fail_closed_when_enforced", "Sync-plan enforcement should fail closed for production safety."));
            risk_score += 10;
        }
    } else {
        checks.push(check("sync_plan_enforcement_shadow", true, "info", json!({"enforce_sync_plan": false, "authority_mode": authority_mode})));
    }

    if execute_apply_manifest || allow_file_writes {
        let file_write_ready = execute_apply_manifest && allow_file_writes && generated_paths_ok && self_test_ready && transport_ok;
        checks.push(check("rust_file_write_authority_ready", file_write_ready, "high", json!({"execute_apply_manifest": execute_apply_manifest, "allow_rust_file_writes": allow_file_writes})));
        if !file_write_ready {
            blockers.push(json!({"code":"file_write_authority_not_ready","message":"Rust file-write flags are partially enabled or prerequisites are missing."}));
            errors.push(err("file_write_authority_not_ready", "rust_core.allow_rust_file_writes", "Rust file-write authority is not ready."));
            risk_score += 35;
        } else if !append_journal || !allow_journal_writes {
            warnings.push(warn("file_write_without_journal", "rust_core.append_transaction_journal", "Rust file-write authority should be paired with transaction journal persistence."));
            risk_score += 15;
        }
    } else {
        checks.push(check("rust_file_write_authority_disabled", true, "info", json!({"execute_apply_manifest": false, "allow_rust_file_writes": false})));
    }

    if allow_libreqos_apply {
        warnings.push(warn("rust_libreqos_apply_not_implemented", "rust_core.allow_rust_libreqos_apply", "Rust transaction executor does not invoke LibreQoS.py in this release; Python remains authoritative for external apply."));
        risk_score += 15;
    }

    if append_journal || allow_journal_writes {
        let journal_ready = append_journal && allow_journal_writes && !transaction_journal_path.is_empty();
        checks.push(check("transaction_journal_persistence_ready", journal_ready, "medium", json!({"append_transaction_journal": append_journal, "allow_transaction_journal_writes": allow_journal_writes, "path": transaction_journal_path, "existing_entries": journal_entries})));
        if !journal_ready {
            blockers.push(json!({"code":"journal_persistence_not_ready","message":"Transaction journal persistence is partially enabled or missing a path."}));
            errors.push(err("journal_persistence_not_ready", "rust_core.append_transaction_journal", "Transaction journal persistence is not ready."));
            risk_score += 25;
        }
        if allow_dry_run_journal {
            warnings.push(warn("dry_run_journal_entries_enabled", "rust_core.allow_dry_run_journal_entries", "Dry Run journal entries are enabled; this can add noisy audit data."));
            risk_score += 5;
        }
        if include_rehearsal_journal {
            warnings.push(warn("rehearsal_journal_entries_enabled", "rust_core.include_rehearsal_journal_entries", "Rehearsal journal entries are enabled; use this only while testing authority migration."));
            risk_score += 3;
        }
    } else {
        checks.push(check("transaction_journal_persistence_disabled", true, "info", json!({"append_transaction_journal": false, "allow_transaction_journal_writes": false, "path": transaction_journal_path}))); 
    }

    if execute_rollback || allow_rollback_writes || rollback_authority == "execute_file_restores" {
        let rollback_ready = execute_rollback && allow_rollback_writes && rollback_authority == "execute_file_restores" && self_test_ready && transport_ok;
        checks.push(check("rollback_authority_ready", rollback_ready, "critical", json!({"execute_rollback": execute_rollback, "allow_rust_rollback_file_writes": allow_rollback_writes, "rollback_authority": rollback_authority})));
        if !rollback_ready {
            blockers.push(json!({"code":"rollback_authority_not_ready","message":"Rollback execution flags are partially enabled or prerequisites are missing."}));
            errors.push(err("rollback_authority_not_ready", "rust_core.rollback_authority", "Rollback authority is not ready."));
            risk_score += 40;
        } else if journal_entries == 0 {
            warnings.push(warn("rollback_authority_no_journal_history", "paths.transaction_journal", "Rollback authority is enabled but no transaction journal entries were reported."));
            risk_score += 12;
        }
    } else {
        checks.push(check("rollback_authority_preview_only", true, "info", json!({"rollback_authority": rollback_authority, "execute_rollback": false}))); 
    }

    if prefer_daemon && !transport_ok {
        warnings.push(warn("daemon_preferred_but_unavailable", "rust_core.prefer_daemon", "Daemon is preferred but transport did not report healthy."));
        risk_score += 10;
    }

    let authority_flags_enabled = enforce_sync_plan
        || authority_mode == "enforce_blockers"
        || execute_apply_manifest
        || allow_file_writes
        || append_journal
        || allow_journal_writes
        || execute_rollback
        || allow_rollback_writes
        || rollback_authority == "execute_file_restores";

    let failed_check_count = checks.iter().filter(|c| !c.get("ok").and_then(Value::as_bool).unwrap_or(false)).count();
    risk_score = std::cmp::min(100, risk_score + (failed_check_count as i64 * 6));
    let risk_level = if risk_score >= 81 { "critical" } else if risk_score >= 51 { "high" } else if risk_score >= 21 { "medium" } else { "low" };

    let verdict = if !blockers.is_empty() || !errors.is_empty() {
        "not_ready"
    } else if !authority_flags_enabled {
        "shadow_safe"
    } else if (execute_apply_manifest && allow_file_writes) || (execute_rollback && allow_rollback_writes) {
        "ready_for_authority_pilot"
    } else if enforce_sync_plan || authority_mode == "enforce_blockers" {
        "ready_for_sync_plan_enforcement"
    } else {
        "ready_with_warnings"
    };

    if verdict == "shadow_safe" {
        recommendations.push(json!({"title":"Shadow mode is healthy","action":"Keep Rust in shadow mode or enable one authority flag at a time after reviewing Dry Run.","severity":"info"}));
    } else if verdict == "ready_for_sync_plan_enforcement" {
        recommendations.push(json!({"title":"Sync-plan gate can be piloted","action":"Enable during a supervised window and verify Dry Run plus Operations diagnostics first.","severity":"warning"}));
    } else if verdict == "ready_for_authority_pilot" {
        recommendations.push(json!({"title":"Authority pilot requires strict change control","action":"Use a small maintenance window, ensure backup and transaction journal persistence, and keep Python fallback available.","severity":"high"}));
    } else {
        recommendations.push(json!({"title":"Resolve readiness blockers","action":"Fix failed checks before enabling Rust authority flags.","severity":"critical"}));
    }

    let result = json!({
        "mode": "authority_readiness",
        "authoritative": false,
        "verdict": verdict,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "ready": errors.is_empty() && blockers.is_empty(),
        "authority_flags_enabled": authority_flags_enabled,
        "check_count": checks.len(),
        "failed_check_count": failed_check_count,
        "checks": checks,
        "blockers": blockers,
        "recommendations": recommendations,
        "journal_summary": {"reported_entries": journal_entries, "path": transaction_journal_path},
        "transport": {"available": rust_available, "ok": status_ok, "prefer_daemon": prefer_daemon},
        "self_test": {"ok": self_test_ok, "status": self_test_status}
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shadow_defaults_are_safe() {
        let payload = json!({
            "config": {
                "rust_core": {"enabled": true, "authority_mode":"shadow"},
                "paths": {"shaped_devices_csv":"/opt/libreqos/src/ShapedDevices.csv", "network_json":"/opt/libreqos/src/network.json", "transaction_journal":"/opt/LQoSync/logs/transaction_journal.jsonl"}
            },
            "rust_core_status": {"available": true, "ok": true},
            "self_test": {"ok": true, "result": {"status": "ok"}}
        });
        let (result, errors, _warnings) = evaluate_authority_readiness_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("shadow_safe"));
        assert_eq!(result.get("ready").and_then(Value::as_bool), Some(true));
    }

    #[test]
    fn partial_file_write_flags_block() {
        let payload = json!({
            "config": {
                "rust_core": {"enabled": true, "execute_apply_manifest": true, "allow_rust_file_writes": false},
                "paths": {"shaped_devices_csv":"/opt/libreqos/src/ShapedDevices.csv", "network_json":"/opt/libreqos/src/network.json"}
            },
            "rust_core_status": {"available": true, "ok": true},
            "self_test": {"ok": true, "result": {"status": "ok"}}
        });
        let (result, errors, _warnings) = evaluate_authority_readiness_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("not_ready"));
    }

    #[test]
    fn full_file_write_pilot_ready_with_journal() {
        let payload = json!({
            "config": {
                "rust_core": {"enabled": true, "execute_apply_manifest": true, "allow_rust_file_writes": true, "append_transaction_journal": true, "allow_transaction_journal_writes": true},
                "paths": {"shaped_devices_csv":"/opt/libreqos/src/ShapedDevices.csv", "network_json":"/opt/libreqos/src/network.json", "transaction_journal":"/opt/LQoSync/logs/transaction_journal.jsonl"}
            },
            "rust_core_status": {"available": true, "ok": true},
            "self_test": {"ok": true, "result": {"status": "ok"}},
            "journal_summary": {"total_count": 3}
        });
        let (result, errors, _warnings) = evaluate_authority_readiness_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("ready_for_authority_pilot"));
    }
}
