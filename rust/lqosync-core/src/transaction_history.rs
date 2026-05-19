use crate::protocol::{Diagnostic, Severity};
use crate::transaction_journal::build_rollback_manifest_payload;
use serde_json::{json, Value};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

fn warning(code: &str, path: Option<String>, message: &str) -> Diagnostic {
    Diagnostic {
        code: code.to_string(),
        severity: Severity::Warning,
        path,
        message: message.to_string(),
        value: None,
        safe_for_cleanup: None,
    }
}

fn str_field<'a>(value: &'a Value, key: &str) -> &'a str {
    value.get(key).and_then(Value::as_str).unwrap_or("")
}

fn bool_filter(payload: &Value, key: &str) -> Option<bool> {
    match payload.get(key) {
        Some(Value::Bool(v)) => Some(*v),
        Some(Value::String(s)) => match s.trim().to_lowercase().as_str() {
            "1" | "true" | "yes" | "on" => Some(true),
            "0" | "false" | "no" | "off" => Some(false),
            _ => None,
        },
        _ => None,
    }
}

fn usize_payload(payload: &Value, key: &str, default_value: usize, max_value: usize) -> usize {
    let raw = payload.get(key).and_then(Value::as_u64).unwrap_or(default_value as u64) as usize;
    raw.min(max_value)
}

fn journal_path(payload: &Value) -> String {
    payload
        .get("path")
        .or_else(|| payload.get("journal_path"))
        .and_then(Value::as_str)
        .unwrap_or("/opt/lqosync/logs/transaction_journal.jsonl")
        .trim()
        .to_string()
}

fn include_raw_event(payload: &Value) -> bool {
    payload.get("include_event").and_then(Value::as_bool)
        .or_else(|| payload.get("include_raw_event").and_then(Value::as_bool))
        .unwrap_or(true)
}

fn summarize_entry(line_number: usize, event: &Value, include_event: bool) -> Value {
    let mut summary = json!({
        "line_number": line_number,
        "journal_id": event.get("journal_id"),
        "generated_at_unix": event.get("generated_at_unix"),
        "event": event.get("event"),
        "mode": event.get("mode"),
        "manifest_id": event.get("manifest_id"),
        "manifest_status": event.get("manifest_status"),
        "transaction_status": event.get("transaction_status"),
        "executed": event.get("executed").and_then(Value::as_bool).unwrap_or(false),
        "write_count": event.get("write_count").and_then(Value::as_u64).unwrap_or(0),
        "operation_count": event.get("operation_count").and_then(Value::as_u64).unwrap_or(0),
        "rollback_available": event.get("rollback_available").and_then(Value::as_bool).unwrap_or(false),
        "policy_verdict": event.get("policy_verdict"),
        "sync_plan_verdict": event.get("sync_plan_verdict"),
        "authority_reason": event.get("authority_gate").and_then(|v| v.get("reason")),
    });
    if include_event {
        if let Some(obj) = summary.as_object_mut() {
            obj.insert("raw_event".to_string(), event.clone());
        }
    }
    summary
}

fn event_matches(payload: &Value, event: &Value) -> bool {
    let journal_id = payload.get("journal_id").and_then(Value::as_str).unwrap_or("").trim();
    let manifest_id = payload.get("manifest_id").and_then(Value::as_str).unwrap_or("").trim();
    let transaction_status = payload.get("transaction_status").and_then(Value::as_str).unwrap_or("").trim();
    let sync_plan_verdict = payload.get("sync_plan_verdict").and_then(Value::as_str).unwrap_or("").trim();
    let executed = bool_filter(payload, "executed");

    if !journal_id.is_empty() && str_field(event, "journal_id") != journal_id {
        return false;
    }
    if !manifest_id.is_empty() && str_field(event, "manifest_id") != manifest_id {
        return false;
    }
    if !transaction_status.is_empty() && str_field(event, "transaction_status") != transaction_status {
        return false;
    }
    if !sync_plan_verdict.is_empty() && event.get("sync_plan_verdict").and_then(Value::as_str).unwrap_or("") != sync_plan_verdict {
        return false;
    }
    if let Some(expected) = executed {
        if event.get("executed").and_then(Value::as_bool).unwrap_or(false) != expected {
            return false;
        }
    }
    true
}

fn read_journal_events(path: &str) -> Result<(Vec<(usize, Value)>, usize, Vec<Diagnostic>), Diagnostic> {
    if path.trim().is_empty() {
        return Err(Diagnostic::error(
            "transaction_journal_path_required",
            Some("path".to_string()),
            "transaction journal path is required",
        ));
    }
    let target = Path::new(path);
    if !target.exists() {
        return Ok((Vec::new(), 0, Vec::new()));
    }
    let file = File::open(target).map_err(|e| Diagnostic::error(
        "transaction_journal_read_failed",
        Some("path".to_string()),
        format!("failed to open transaction journal: {e}"),
    ))?;
    let reader = BufReader::new(file);
    let mut entries: Vec<(usize, Value)> = Vec::new();
    let mut invalid = 0usize;
    let mut warnings = Vec::new();
    for (idx, line) in reader.lines().enumerate() {
        let line_number = idx + 1;
        let line = match line {
            Ok(v) => v,
            Err(e) => {
                invalid += 1;
                warnings.push(warning(
                    "transaction_journal_line_read_failed",
                    Some(format!("line[{line_number}]")),
                    &format!("failed to read transaction journal line {line_number}: {e}"),
                ));
                continue;
            }
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        match serde_json::from_str::<Value>(trimmed) {
            Ok(v) if v.is_object() => entries.push((line_number, v)),
            Ok(_) => {
                invalid += 1;
                warnings.push(warning(
                    "transaction_journal_line_not_object",
                    Some(format!("line[{line_number}]")),
                    "transaction journal line is valid JSON but not an object",
                ));
            }
            Err(e) => {
                invalid += 1;
                warnings.push(warning(
                    "transaction_journal_invalid_jsonl",
                    Some(format!("line[{line_number}]")),
                    &format!("invalid transaction journal JSONL at line {line_number}: {e}"),
                ));
            }
        }
    }
    Ok((entries, invalid, warnings))
}

/// Read and filter the Rust transaction journal JSONL file.
///
/// This operation is read-only. It is intended for the WebUI/Operations Center
/// to inspect previous Rust transaction previews/executions without shelling out
/// to jq or manually opening JSONL logs.
pub fn read_transaction_journal_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let path = journal_path(payload);
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let limit = usize_payload(payload, "limit", 50, 500);
    let offset = usize_payload(payload, "offset", 0, 50_000);
    let reverse = payload.get("reverse").and_then(Value::as_bool).unwrap_or(true);
    let include_event = include_raw_event(payload);

    let (entries, invalid_line_count, read_warnings) = match read_journal_events(&path) {
        Ok(v) => v,
        Err(e) => {
            errors.push(e);
            return (json!({
                "mode": "transaction_journal_reader",
                "status": "failed",
                "path": path,
                "entries": [],
                "returned_count": 0,
            }), errors, warnings);
        }
    };
    warnings.extend(read_warnings);

    let status = if !Path::new(&path).exists() { "missing" } else { "ok" };
    let mut matched: Vec<(usize, Value)> = entries
        .iter()
        .filter(|(_, event)| event_matches(payload, event))
        .map(|(line_number, event)| (*line_number, event.clone()))
        .collect();
    if reverse {
        matched.reverse();
    }
    let returned: Vec<Value> = matched
        .iter()
        .skip(offset)
        .take(limit)
        .map(|(line_number, event)| summarize_entry(*line_number, event, include_event))
        .collect();

    let result = json!({
        "mode": "transaction_journal_reader",
        "authoritative": false,
        "read_only": true,
        "status": status,
        "path": path,
        "limit": limit,
        "offset": offset,
        "reverse": reverse,
        "include_event": include_event,
        "filters": {
            "journal_id": payload.get("journal_id"),
            "manifest_id": payload.get("manifest_id"),
            "transaction_status": payload.get("transaction_status"),
            "sync_plan_verdict": payload.get("sync_plan_verdict"),
            "executed": payload.get("executed"),
        },
        "total_line_count": entries.len() + invalid_line_count,
        "parsed_count": entries.len(),
        "invalid_line_count": invalid_line_count,
        "matched_count": matched.len(),
        "returned_count": returned.len(),
        "entries": returned,
    });
    (result, errors, warnings)
}

/// Build a rollback manifest by selecting a journal entry from transaction_journal.jsonl.
///
/// This is still preview-only. It reads a historical journal event and passes the
/// embedded manifest/transaction to build-rollback-manifest. It does not restore
/// files and does not execute rollback actions.
pub fn build_rollback_from_journal_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let path = journal_path(payload);
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let journal_id = payload.get("journal_id").and_then(Value::as_str).unwrap_or("").trim();
    let manifest_id = payload.get("manifest_id").and_then(Value::as_str).unwrap_or("").trim();
    if journal_id.is_empty() && manifest_id.is_empty() {
        errors.push(Diagnostic::error(
            "rollback_journal_selector_required",
            Some("journal_id".to_string()),
            "Provide journal_id or manifest_id to build a rollback plan from the journal.",
        ));
        return (json!({"mode":"rollback_from_journal", "status":"selector_required", "path": path}), errors, warnings);
    }

    let (entries, invalid_line_count, read_warnings) = match read_journal_events(&path) {
        Ok(v) => v,
        Err(e) => {
            errors.push(e);
            return (json!({"mode":"rollback_from_journal", "status":"failed", "path": path}), errors, warnings);
        }
    };
    warnings.extend(read_warnings);
    if invalid_line_count > 0 {
        warnings.push(warning(
            "transaction_journal_contains_invalid_lines",
            Some("path".to_string()),
            "Transaction journal contains invalid JSONL lines; valid entries were still inspected.",
        ));
    }

    let mut selected: Option<(usize, Value)> = None;
    for (line_number, event) in entries.into_iter() {
        if event_matches(payload, &event) {
            selected = Some((line_number, event));
        }
    }
    let Some((line_number, event)) = selected else {
        errors.push(Diagnostic::error(
            "transaction_journal_entry_not_found",
            Some("journal_id".to_string()),
            "No transaction journal entry matched the requested journal_id/manifest_id.",
        ));
        return (json!({
            "mode": "rollback_from_journal",
            "status": "not_found",
            "path": path,
            "journal_id": journal_id,
            "manifest_id": manifest_id,
        }), errors, warnings);
    };

    let rollback_payload = json!({
        "manifest": event.get("manifest").cloned().unwrap_or_else(|| json!({})),
        "transaction": event.get("transaction").cloned().unwrap_or_else(|| json!({})),
        "rust_transaction_journal": {"result": event.clone()},
    });
    let (mut rollback, rollback_errors, rollback_warnings) = build_rollback_manifest_payload(&rollback_payload);
    errors.extend(rollback_errors);
    warnings.extend(rollback_warnings);
    if let Some(obj) = rollback.as_object_mut() {
        obj.insert("source".to_string(), json!("transaction_journal"));
        obj.insert("journal_path".to_string(), json!(path));
        obj.insert("journal_line_number".to_string(), json!(line_number));
        obj.insert("journal_id".to_string(), event.get("journal_id").cloned().unwrap_or(Value::Null));
        obj.insert("selected_manifest_id".to_string(), event.get("manifest_id").cloned().unwrap_or(Value::Null));
        obj.insert("selected_transaction_status".to_string(), event.get("transaction_status").cloned().unwrap_or(Value::Null));
    }
    (rollback, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn temp_journal_path(name: &str) -> String {
        let mut p = std::env::temp_dir();
        p.push(format!("lqosync-core-{name}-{}-{}.jsonl", std::process::id(), crate::atomic_state::sha256_text(name)));
        p.to_string_lossy().to_string()
    }

    #[test]
    fn reads_and_filters_transaction_journal() {
        let path = temp_journal_path("journal-read");
        let event = json!({
            "event":"rust_apply_transaction_journal",
            "journal_id":"txj-test",
            "manifest_id":"manifest-test",
            "transaction_status":"completed",
            "executed":true,
            "write_count":2,
            "operation_count":3,
            "rollback_available":true,
            "transaction":{"executed":true,"status":"completed","write_results":[]},
            "manifest":{"manifest_id":"manifest-test","status":"ready"}
        });
        fs::write(&path, format!("{}\n", serde_json::to_string(&event).unwrap())).unwrap();
        let (result, errors, warnings) = read_transaction_journal_payload(&json!({"path": path, "journal_id":"txj-test"}));
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert!(warnings.is_empty(), "warnings: {warnings:?}");
        assert_eq!(result.get("returned_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("entries").and_then(Value::as_array).unwrap()[0].get("journal_id").and_then(Value::as_str), Some("txj-test"));
    }

    #[test]
    fn builds_rollback_plan_from_journal_entry() {
        let path = temp_journal_path("journal-rollback");
        let event = json!({
            "event":"rust_apply_transaction_journal",
            "journal_id":"txj-rollback",
            "manifest_id":"manifest-rollback",
            "transaction_status":"completed",
            "executed":true,
            "write_count":1,
            "rollback_available":true,
            "transaction":{
                "executed":true,
                "status":"completed",
                "write_results":[{"path":"/tmp/target.csv","backup_path":"/tmp/target.csv.bak","after_sha256":"after","before_sha256":"before","file_kind":"csv"}]
            },
            "manifest":{"manifest_id":"manifest-rollback","status":"ready"}
        });
        fs::write(&path, format!("{}\n", serde_json::to_string(&event).unwrap())).unwrap();
        let (result, errors, _warnings) = build_rollback_from_journal_payload(&json!({"path": path, "journal_id":"txj-rollback"}));
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("rollback_available").and_then(Value::as_bool), Some(true));
        assert_eq!(result.get("operation_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("source").and_then(Value::as_str), Some("transaction_journal"));
    }
}
