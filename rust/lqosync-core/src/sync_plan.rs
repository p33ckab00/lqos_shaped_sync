use crate::protocol::{Diagnostic, Severity};
use serde_json::{json, Value};

fn risk_level(score: i64) -> &'static str {
    if score >= 81 {
        "critical"
    } else if score >= 51 {
        "high"
    } else if score >= 21 {
        "medium"
    } else {
        "low"
    }
}

fn diagnostic_count(value: &Value, key: &str) -> usize {
    value.get(key).and_then(Value::as_array).map(|v| v.len()).unwrap_or(0)
}

fn result_obj(value: &Value) -> Value {
    value.get("result").cloned().unwrap_or_else(|| json!({}))
}

fn bool_path(value: &Value, path: &[&str], default: bool) -> bool {
    let mut current = value;
    for part in path {
        match current.get(*part) {
            Some(next) => current = next,
            None => return default,
        }
    }
    current.as_bool().unwrap_or(default)
}

fn int_path(value: &Value, path: &[&str], default: i64) -> i64 {
    let mut current = value;
    for part in path {
        match current.get(*part) {
            Some(next) => current = next,
            None => return default,
        }
    }
    current.as_i64().or_else(|| current.as_u64().map(|v| v as i64)).unwrap_or(default)
}

fn str_path<'a>(value: &'a Value, path: &[&str], default: &'a str) -> &'a str {
    let mut current = value;
    for part in path {
        match current.get(*part) {
            Some(next) => current = next,
            None => return default,
        }
    }
    current.as_str().unwrap_or(default)
}

pub fn evaluate_sync_plan_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let mut blockers: Vec<Value> = Vec::new();
    let mut holds: Vec<Value> = Vec::new();
    let mut next_actions: Vec<Value> = Vec::new();
    let mut trace: Vec<Value> = Vec::new();
    let mut risk_score: i64 = 0;

    let mode = payload.get("mode").and_then(Value::as_str).unwrap_or("apply");
    let files_changed = payload.get("files_changed").and_then(Value::as_bool).unwrap_or(false);
    let csv_changed = payload.get("csv_changed").and_then(Value::as_bool).unwrap_or(false);
    let network_changed = payload.get("network_changed").and_then(Value::as_bool).unwrap_or(false);
    let rust_validation = payload.get("rust_validation").cloned().unwrap_or_else(|| json!({}));
    let rust_diff = payload.get("rust_diff").cloned().unwrap_or_else(|| json!({}));
    let rust_policy = payload.get("rust_policy_shadow").cloned().unwrap_or_else(|| json!({}));
    let rust_circuit = payload.get("rust_circuit_shadow").cloned().unwrap_or_else(|| json!({}));
    let preflight = payload.get("preflight").cloned().unwrap_or_else(|| json!({}));
    let cleanup = payload.get("cleanup").cloned().unwrap_or_else(|| json!({}));
    let collector_trust = payload.get("collector_trust").and_then(Value::as_array).cloned().unwrap_or_default();

    let validation_errors = diagnostic_count(&rust_validation, "errors");
    if validation_errors > 0 || rust_validation.get("ok").and_then(Value::as_bool) == Some(false) {
        risk_score += 35;
        blockers.push(json!({
            "code": "rust_validation_failed",
            "title": "Rust validation reported errors",
            "message": "Proposed CSV/network output failed Rust validation.",
            "severity": "critical",
            "count": validation_errors,
        }));
        errors.push(Diagnostic::error(
            "sync_plan_validation_blocker",
            Some("rust_validation".to_string()),
            "Rust validation errors block the shadow sync plan".to_string(),
        ));
        trace.push(json!({"step": "validation", "decision": "block", "errors": validation_errors}));
    } else {
        trace.push(json!({"step": "validation", "decision": "ok", "errors": 0}));
    }

    let preflight_errors = preflight.get("errors").and_then(Value::as_array).map(|v| v.len()).unwrap_or(0);
    if preflight_errors > 0 {
        risk_score += 35;
        blockers.push(json!({
            "code": "preflight_failed",
            "title": "Python preflight reported errors",
            "message": "The authoritative Python preflight returned one or more errors.",
            "severity": "critical",
            "count": preflight_errors,
        }));
        trace.push(json!({"step": "preflight", "decision": "block", "errors": preflight_errors}));
    } else {
        trace.push(json!({"step": "preflight", "decision": "ok"}));
    }

    let mut unsafe_collectors = Vec::new();
    for item in collector_trust.iter() {
        let res = result_obj(item);
        let safe = res.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(true);
        if !safe {
            let router = res.get("router").and_then(Value::as_str).unwrap_or("unknown");
            let source = res.get("source").and_then(Value::as_str).unwrap_or("unknown");
            unsafe_collectors.push(format!("{router}/{source}"));
        }
    }
    if !unsafe_collectors.is_empty() {
        risk_score += 25;
        holds.push(json!({
            "code": "collector_cleanup_held",
            "title": "Collector cleanup held",
            "message": "One or more collectors are not trusted for cleanup.",
            "severity": "high",
            "sources": unsafe_collectors,
        }));
        warnings.push(Diagnostic {
            code: "sync_plan_collector_cleanup_held".to_string(),
            severity: Severity::Warning,
            path: Some("collector_trust".to_string()),
            message: "One or more collector outputs are not trusted for cleanup".to_string(),
            value: None,
            safe_for_cleanup: Some(false),
        });
        trace.push(json!({"step": "collector_trust", "decision": "hold_cleanup"}));
    } else {
        trace.push(json!({"step": "collector_trust", "decision": "ok"}));
    }

    let policy_result = result_obj(&rust_policy);
    let policy_verdict = policy_result.get("verdict").and_then(Value::as_str).unwrap_or("unknown");
    let policy_risk_score = policy_result.get("risk_score").and_then(Value::as_i64).unwrap_or(0);
    risk_score = risk_score.max(policy_risk_score);
    if policy_verdict == "blocked_by_policy" {
        risk_score += 30;
        blockers.push(json!({
            "code": "policy_shadow_blocked",
            "title": "Rust policy shadow blocked",
            "message": "Rust policy shadow returned blocked_by_policy. Python policy remains authoritative.",
            "severity": "high",
        }));
        trace.push(json!({"step": "policy_shadow", "decision": "block_hint", "verdict": policy_verdict}));
    } else if policy_verdict == "apply_with_caution" {
        risk_score += 12;
        holds.push(json!({
            "code": "policy_shadow_caution",
            "title": "Rust policy shadow recommends caution",
            "message": "Rust policy shadow returned apply_with_caution.",
            "severity": "warning",
        }));
        trace.push(json!({"step": "policy_shadow", "decision": "caution", "verdict": policy_verdict}));
    } else {
        trace.push(json!({"step": "policy_shadow", "decision": "ok", "verdict": policy_verdict}));
    }

    let circuit_errors = diagnostic_count(&rust_circuit, "errors");
    let circuit_warnings = diagnostic_count(&rust_circuit, "warnings");
    if circuit_errors > 0 {
        risk_score += 25;
        blockers.push(json!({
            "code": "circuit_shadow_errors",
            "title": "Rust circuit shadow reported errors",
            "message": "Circuit normalization shadow reported invalid circuit rows.",
            "severity": "high",
            "count": circuit_errors,
        }));
        trace.push(json!({"step": "circuit_shadow", "decision": "block_hint", "errors": circuit_errors}));
    } else if circuit_warnings > 0 {
        risk_score += 8;
        trace.push(json!({"step": "circuit_shadow", "decision": "warning", "warnings": circuit_warnings}));
    } else {
        trace.push(json!({"step": "circuit_shadow", "decision": "ok"}));
    }

    let csv_change_count = int_path(&rust_diff, &["result", "csv", "added_count"], 0)
        + int_path(&rust_diff, &["result", "csv", "updated_count"], 0)
        + int_path(&rust_diff, &["result", "csv", "removed_count"], 0);
    let network_changed_rust = bool_path(&rust_diff, &["result", "network", "changed"], network_changed);
    if csv_change_count > 0 || network_changed_rust {
        risk_score += if csv_change_count > 20 { 18 } else { 6 };
        trace.push(json!({"step": "diff", "decision": "changes_detected", "csv_changes": csv_change_count, "network_changed": network_changed_rust}));
    } else {
        trace.push(json!({"step": "diff", "decision": "no_changes"}));
    }

    let removed = cleanup.get("removed").and_then(Value::as_i64).unwrap_or(0);
    let queued = cleanup.get("queued").and_then(Value::as_i64).unwrap_or(0);
    if removed > 0 {
        risk_score += (removed * 3).min(18);
        holds.push(json!({
            "code": "cleanup_removal_present",
            "title": "Cleanup removes rows",
            "message": format!("Cleanup would remove {removed} row(s)."),
            "severity": if removed >= 10 { "high" } else { "warning" },
            "affected_rows": removed,
        }));
    }
    if queued > 0 {
        risk_score += 5;
    }

    let dry_run = mode == "dry_run";
    let mut write_allowed = blockers.is_empty() && !dry_run;
    let mut apply_allowed = blockers.is_empty() && !dry_run && files_changed;
    let cleanup_allowed = !holds.iter().any(|h| h.get("code").and_then(Value::as_str) == Some("collector_cleanup_held")) && blockers.is_empty();

    if dry_run {
        next_actions.push(json!({
            "title": "Review Dry Run",
            "action": "Inspect Rust/Python shadow diagnostics before switching to apply mode.",
            "severity": "info",
        }));
    } else if blockers.is_empty() && files_changed {
        next_actions.push(json!({
            "title": "Apply candidate",
            "action": "Python remains authoritative; this Rust plan agrees there are no shadow blockers.",
            "severity": "info",
        }));
    } else if blockers.is_empty() && !files_changed {
        apply_allowed = false;
        write_allowed = false;
        next_actions.push(json!({
            "title": "No file changes",
            "action": "No generated file write/apply is needed.",
            "severity": "info",
        }));
    } else {
        next_actions.push(json!({
            "title": "Resolve blockers",
            "action": "Review validation, collector trust, circuit shadow, and policy diagnostics before applying.",
            "severity": "critical",
        }));
    }

    let risk_score = risk_score.min(100);
    let risk_level = risk_level(risk_score);
    let verdict = if !blockers.is_empty() || risk_level == "critical" {
        write_allowed = false;
        apply_allowed = false;
        "blocked_by_shadow_plan"
    } else if !holds.is_empty() || risk_level == "medium" || risk_level == "high" {
        "manual_review_recommended"
    } else if !files_changed {
        "no_changes"
    } else {
        "ready_by_shadow_plan"
    };

    let result = json!({
        "mode": "shadow",
        "authoritative": false,
        "transport_safe": true,
        "input_mode": mode,
        "verdict": verdict,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "write_allowed": write_allowed,
        "apply_allowed": apply_allowed,
        "cleanup_allowed": cleanup_allowed,
        "files_changed": files_changed,
        "csv_changed": csv_changed,
        "network_changed": network_changed,
        "summary": {
            "csv_change_count": csv_change_count,
            "network_changed": network_changed_rust,
            "collector_checks": collector_trust.len(),
            "blocked_count": blockers.len(),
            "hold_count": holds.len(),
            "validation_errors": validation_errors,
            "preflight_errors": preflight_errors,
            "circuit_errors": circuit_errors,
            "policy_verdict": policy_verdict,
            "policy_risk_level": str_path(&rust_policy, &["result", "risk_level"], "unknown"),
        },
        "blockers": blockers,
        "holds": holds,
        "next_actions": next_actions,
        "decision_trace": trace,
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn marks_no_changes_as_no_changes() {
        let (result, errors, _warnings) = evaluate_sync_plan_payload(&json!({
            "mode": "apply",
            "files_changed": false,
            "rust_validation": {"ok": true, "errors": []},
            "preflight": {"errors": []},
            "rust_policy_shadow": {"result": {"verdict": "safe_to_apply", "risk_score": 0, "risk_level": "low"}},
            "rust_circuit_shadow": {"errors": [], "warnings": []},
            "collector_trust": []
        }));
        assert!(errors.is_empty());
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("no_changes"));
        assert_eq!(result.get("apply_allowed").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_on_validation_errors() {
        let (result, errors, _warnings) = evaluate_sync_plan_payload(&json!({
            "mode": "apply",
            "files_changed": true,
            "rust_validation": {"ok": false, "errors": [{"code": "bad"}]},
            "preflight": {"errors": []},
            "rust_policy_shadow": {"result": {"verdict": "safe_to_apply", "risk_score": 0, "risk_level": "low"}},
            "rust_circuit_shadow": {"errors": [], "warnings": []},
            "collector_trust": []
        }));
        assert!(!errors.is_empty());
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("blocked_by_shadow_plan"));
        assert_eq!(result.get("write_allowed").and_then(Value::as_bool), Some(false));
    }
}
