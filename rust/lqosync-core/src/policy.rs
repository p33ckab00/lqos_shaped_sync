use crate::protocol::{Diagnostic, Severity};
use serde_json::{json, Value};

const RISK_LOW_MAX: i64 = 20;
const RISK_MEDIUM_MAX: i64 = 50;
const RISK_HIGH_MAX: i64 = 80;

pub fn evaluate_policy_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let null = Value::Null;
    let config = payload.get("config").unwrap_or(&null);
    let preflight = payload.get("preflight").unwrap_or(&null);
    let collector_trust = payload.get("collector_trust").unwrap_or(&null);
    let cleanup = payload.get("cleanup").unwrap_or(&null);
    let rust_validation = payload.get("rust_validation").unwrap_or(&null);
    let python_decision = payload.get("python_policy_decision").unwrap_or(&null);

    let mut blocked_reasons: Vec<Value> = Vec::new();
    let mut warnings_out: Vec<Value> = Vec::new();
    let mut recommendations: Vec<Value> = Vec::new();
    let mut decision_trace: Vec<Value> = Vec::new();
    let diagnostics_errors: Vec<Diagnostic> = Vec::new();
    let mut diagnostics_warnings: Vec<Diagnostic> = Vec::new();
    let mut risk_score: i64 = 0;
    let mut cleanup_allowed = true;
    let mut write_allowed = true;
    let mut apply_allowed = true;

    let apply_guard = config.pointer("/policies/apply_guard").unwrap_or(&Value::Null);
    let collector_guard = config.pointer("/policies/collector_guard").unwrap_or(&Value::Null);

    let preflight_errors = string_array(preflight.get("errors"));
    let preflight_warnings = string_array(preflight.get("warnings"));
    if !preflight_errors.is_empty() {
        let joined = preflight_errors.join("\n").to_lowercase();
        let mut matched_specific = false;
        if bool_at(apply_guard, "block_apply_on_duplicate_ip", true) && joined.contains("duplicate ip") {
            add_block(&mut blocked_reasons, &mut decision_trace, "duplicate_ip", "Duplicate IP detected", "Preflight detected duplicate IP addresses.");
            matched_specific = true;
        }
        if bool_at(apply_guard, "block_apply_on_missing_parent", true) && joined.contains("parent") {
            add_block(&mut blocked_reasons, &mut decision_trace, "missing_parent", "Missing parent node", "One or more circuits reference missing Parent Node values.");
            matched_specific = true;
        }
        if bool_at(apply_guard, "block_apply_on_invalid_speed", true) && (joined.contains("bandwidth") || joined.contains("speed")) {
            add_block(&mut blocked_reasons, &mut decision_trace, "invalid_speed", "Invalid speed/bandwidth", "Preflight detected invalid speed or bandwidth values.");
            matched_specific = true;
        }
        if !matched_specific {
            add_block(&mut blocked_reasons, &mut decision_trace, "preflight_errors", "Preflight errors", "Preflight returned one or more errors.");
        }
        risk_score += 35;
    }
    if !preflight_warnings.is_empty() {
        risk_score += (preflight_warnings.len() as i64).min(5) * 5;
        warnings_out.push(json!({
            "title": "Preflight warnings present",
            "message": format!("{} preflight warning(s) were reported.", preflight_warnings.len()),
            "severity": "warning"
        }));
        decision_trace.push(json!({"policy":"preflight", "decision":"warnings_present", "count":preflight_warnings.len()}));
    }

    let trust_items = collector_trust.as_array().cloned().unwrap_or_default();
    let mut unsafe_sources = Vec::new();
    for item in &trust_items {
        let result = item.get("result").unwrap_or(item);
        let safe = result.get("safe_for_cleanup").and_then(Value::as_bool).unwrap_or(true);
        if !safe {
            let router = result.get("router").and_then(Value::as_str).unwrap_or("unknown");
            let source = result.get("source").and_then(Value::as_str).unwrap_or("unknown");
            unsafe_sources.push(format!("{router}/{source}"));
        }
    }
    if !unsafe_sources.is_empty() {
        cleanup_allowed = false;
        risk_score += 25;
        let unsafe_count = unsafe_sources.len();
        warnings_out.push(json!({
            "title": "Collector cleanup held",
            "message": format!("Unsafe collector output held cleanup for: {}", unsafe_sources.join(", ")),
            "severity": "high",
            "sources": unsafe_sources.clone(),
        }));
        decision_trace.push(json!({"policy":"collector_trust", "decision":"cleanup_held", "unsafe_count": unsafe_count}));
        if bool_at(apply_guard, "block_apply_on_collector_failure", true)
            || bool_at(collector_guard, "block_cleanup_if_source_failed", true)
        {
            add_block(&mut blocked_reasons, &mut decision_trace, "collector_not_trusted", "Collector trust failure", "One or more collector outputs were not trusted for cleanup/apply.");
        }
    }

    let rust_ok = rust_validation.get("ok").and_then(Value::as_bool).unwrap_or(true);
    let rust_errors = rust_validation.get("errors").and_then(Value::as_array).map(|v| v.len()).unwrap_or(0);
    if !rust_ok || rust_errors > 0 {
        risk_score += 30;
        add_block(&mut blocked_reasons, &mut decision_trace, "rust_validation_failed", "Rust validation failed", "Rust validation reported errors in proposed output.");
    }

    let removed = number_at(cleanup, "removed");
    let queued = number_at(cleanup, "queued");
    let preserved = number_at(cleanup, "preserved");
    let candidates = number_at(cleanup, "candidates");
    if removed > 0 {
        risk_score += (removed * 4).min(25);
        warnings_out.push(json!({
            "title": "Rows removed by cleanup",
            "message": format!("{} row(s) are scheduled for removal by cleanup policy.", removed),
            "severity": if removed >= 10 { "high" } else { "warning" },
            "affected_rows": removed,
        }));
        decision_trace.push(json!({"policy":"cleanup", "decision":"rows_removed", "removed":removed}));
    }
    if queued > 0 || preserved > 0 {
        risk_score += ((queued + preserved) * 2).min(20);
        decision_trace.push(json!({"policy":"cleanup", "decision":"queued_or_preserved", "queued":queued, "preserved":preserved}));
    }
    if candidates > 0 && removed == 0 && queued == 0 && preserved == 0 {
        risk_score += 8;
        warnings_out.push(json!({
            "title": "Cleanup candidates detected",
            "message": format!("{} cleanup candidate(s) were detected but no removal/queue/preserve action was summarized.", candidates),
            "severity": "warning",
            "affected_rows": candidates,
        }));
    }

    if !blocked_reasons.is_empty() {
        write_allowed = false;
        apply_allowed = false;
        cleanup_allowed = false;
    }

    risk_score += (blocked_reasons.len() as i64) * 30;
    risk_score += warnings_out.iter().filter(|w| w.get("severity").and_then(Value::as_str).unwrap_or("") == "high").count() as i64 * 12;
    if risk_score > 100 { risk_score = 100; }
    let risk_level = risk_level_for_score(risk_score);
    let mut verdict = if !blocked_reasons.is_empty() {
        "blocked_by_policy"
    } else if risk_level == "medium" || risk_level == "high" {
        "apply_with_caution"
    } else if risk_level == "critical" {
        "blocked_by_policy"
    } else {
        "safe_to_apply"
    };
    if risk_level == "critical" {
        verdict = "blocked_by_policy";
        write_allowed = false;
        apply_allowed = false;
        cleanup_allowed = false;
    }

    if !write_allowed {
        recommendations.push(json!({
            "title": "Review blocked policy decision",
            "reason": "Rust policy shadow found blocking conditions.",
            "action": "Review Dry Run diagnostics, collector trust, and preflight errors before applying.",
            "severity": "critical"
        }));
    } else if risk_level != "low" {
        recommendations.push(json!({
            "title": "Review medium/high risk change",
            "reason": format!("Rust policy shadow classified this run as {risk_level} risk."),
            "action": "Review Dry Run diff and policy warnings before enabling auto-apply.",
            "severity": "warning"
        }));
    }

    let parity = compare_python_decision(python_decision, verdict, risk_level, write_allowed, apply_allowed);
    if !parity.get("matches_verdict").and_then(Value::as_bool).unwrap_or(true) {
        warnings_out.push(json!({
            "title": "Policy parity mismatch",
            "message": "Rust shadow policy verdict differs from Python policy verdict. Python remains authoritative in this release.",
            "severity": "warning",
            "python_verdict": python_decision.get("verdict").cloned().unwrap_or(Value::Null),
            "rust_verdict": verdict,
        }));
        diagnostics_warnings.push(Diagnostic {
            code: "policy_shadow_parity_mismatch".to_string(),
            severity: Severity::Warning,
            path: Some("policy.shadow.verdict".to_string()),
            message: "Rust shadow policy verdict differs from Python policy verdict".to_string(),
            value: Some(parity.clone()),
            safe_for_cleanup: None,
        });
    }

    let result = json!({
        "verdict": verdict,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "apply_allowed": apply_allowed,
        "write_allowed": write_allowed,
        "cleanup_allowed": cleanup_allowed,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings_out,
        "recommendations": recommendations,
        "decision_trace": decision_trace,
        "parity": parity,
        "mode": "shadow",
        "authoritative": false,
    });

    (result, diagnostics_errors, diagnostics_warnings)
}

fn bool_at(value: &Value, key: &str, default: bool) -> bool {
    value.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn number_at(value: &Value, key: &str) -> i64 {
    value.get(key).and_then(Value::as_i64)
        .or_else(|| value.get(key).and_then(Value::as_u64).map(|v| v as i64))
        .or_else(|| value.get(key).and_then(Value::as_f64).map(|v| v.round() as i64))
        .unwrap_or(0)
}

fn string_array(value: Option<&Value>) -> Vec<String> {
    value.and_then(Value::as_array).map(|items| {
        items.iter().map(|item| {
            item.as_str().map(str::to_string).unwrap_or_else(|| item.to_string())
        }).collect()
    }).unwrap_or_default()
}

fn risk_level_for_score(score: i64) -> &'static str {
    if score > RISK_HIGH_MAX { "critical" }
    else if score > RISK_MEDIUM_MAX { "high" }
    else if score > RISK_LOW_MAX { "medium" }
    else { "low" }
}

fn add_block(blocked: &mut Vec<Value>, trace: &mut Vec<Value>, code: &str, title: &str, message: &str) {
    blocked.push(json!({"code":code, "title":title, "message":message, "severity":"critical"}));
    trace.push(json!({"policy":code, "decision":"block", "message":message}));
}

fn compare_python_decision(python_decision: &Value, verdict: &str, risk_level: &str, write_allowed: bool, apply_allowed: bool) -> Value {
    if !python_decision.is_object() {
        return json!({"available": false});
    }
    let py_verdict = python_decision.get("verdict").and_then(Value::as_str).unwrap_or("");
    let py_risk = python_decision.get("risk_level").and_then(Value::as_str).unwrap_or("");
    let py_write = python_decision.get("write_allowed").and_then(Value::as_bool).unwrap_or(true);
    let py_apply = python_decision.get("apply_allowed").and_then(Value::as_bool).unwrap_or(true);
    json!({
        "available": true,
        "matches_verdict": py_verdict == verdict,
        "matches_risk_level": py_risk == risk_level,
        "matches_write_allowed": py_write == write_allowed,
        "matches_apply_allowed": py_apply == apply_allowed,
        "python": {
            "verdict": py_verdict,
            "risk_level": py_risk,
            "write_allowed": py_write,
            "apply_allowed": py_apply,
        },
        "rust": {
            "verdict": verdict,
            "risk_level": risk_level,
            "write_allowed": write_allowed,
            "apply_allowed": apply_allowed,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocks_missing_parent_preflight() {
        let payload = json!({
            "config": {"policies":{"apply_guard":{"block_apply_on_missing_parent":true}}},
            "preflight": {"errors":["Missing Parent Node for client1"], "warnings":[]},
            "cleanup": {"candidates":0,"removed":0,"queued":0,"preserved":0},
            "python_policy_decision": {"verdict":"blocked_by_policy","risk_level":"critical","write_allowed":false,"apply_allowed":false}
        });
        let (result, _errors, _warnings) = evaluate_policy_payload(&payload);
        assert_eq!(result.get("write_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("apply_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("verdict").and_then(Value::as_str), Some("blocked_by_policy"));
    }

    #[test]
    fn warns_on_unsafe_collector() {
        let payload = json!({
            "config": {"policies":{"apply_guard":{"block_apply_on_collector_failure":true}}},
            "collector_trust": [{"result":{"router":"R1","source":"PPP","safe_for_cleanup":false}}],
            "cleanup": {"candidates":5,"removed":0,"queued":0,"preserved":5}
        });
        let (result, _errors, _warnings) = evaluate_policy_payload(&payload);
        assert_eq!(result.get("cleanup_allowed").and_then(Value::as_bool), Some(false));
        assert_eq!(result.get("write_allowed").and_then(Value::as_bool), Some(false));
    }
}
