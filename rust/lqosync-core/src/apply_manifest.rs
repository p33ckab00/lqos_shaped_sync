use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

fn sha256_text(text: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    hex::encode(hasher.finalize())
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

fn result_obj(value: &Value) -> Value {
    value.get("result").cloned().unwrap_or_else(|| json!({}))
}

fn compact_hash(value: &Value) -> String {
    sha256_text(&serde_json::to_string(value).unwrap_or_default())
}

pub fn build_apply_manifest_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let mut operations: Vec<Value> = Vec::new();
    let mut trace: Vec<Value> = Vec::new();

    let mode = payload.get("mode").and_then(Value::as_str).unwrap_or("apply");
    let dry_run = mode == "dry_run";
    let config = payload.get("config").cloned().unwrap_or_else(|| json!({}));
    let state = payload.get("state").cloned().unwrap_or_else(|| json!({}));
    let paths = payload.get("paths").cloned().unwrap_or_else(|| config.get("paths").cloned().unwrap_or_else(|| json!({})));
    let current_csv = payload.get("current_csv_text").and_then(Value::as_str).unwrap_or("");
    let proposed_csv = payload.get("proposed_csv_text").and_then(Value::as_str).unwrap_or("");
    let current_network = payload.get("current_network_text").and_then(Value::as_str).unwrap_or("{}");
    let proposed_network = payload.get("proposed_network_text").and_then(Value::as_str).unwrap_or("{}");

    let csv_path = str_path(&paths, &["shaped_devices_csv"], "");
    let network_path = str_path(&paths, &["network_json"], "");
    let backup_dir = str_path(&paths, &["backup_dir"], "");
    let state_path = str_path(&paths, &["runtime_state"], "");

    let computed_csv_changed = current_csv != proposed_csv;
    let computed_network_changed = current_network != proposed_network;
    let csv_changed = payload.get("csv_changed").and_then(Value::as_bool).unwrap_or(computed_csv_changed);
    let network_changed = payload.get("network_changed").and_then(Value::as_bool).unwrap_or(computed_network_changed);
    let files_changed = payload.get("files_changed").and_then(Value::as_bool).unwrap_or(csv_changed || network_changed);

    let backup_before_apply = bool_path(&config, &["app", "backup_before_apply"], false);
    let auto_apply = bool_path(&config, &["app", "auto_apply"], true);
    let retry_failed = bool_path(&config, &["libreqos", "retry_if_last_apply_failed"], true);
    let pending_apply = bool_path(&state, &["pending_libreqos_apply"], false) || bool_path(&state, &["last_libreqos_apply_failed"], false);

    let policy = payload.get("policy_decision").cloned().unwrap_or_else(|| json!({}));
    let policy_write_allowed = policy.get("write_allowed").and_then(Value::as_bool).unwrap_or(true);
    let policy_apply_allowed = policy.get("apply_allowed").and_then(Value::as_bool).unwrap_or(true);
    let sync_plan = payload.get("rust_sync_plan").cloned().unwrap_or_else(|| json!({}));
    let sync_result = result_obj(&sync_plan);
    let sync_verdict = sync_result.get("verdict").and_then(Value::as_str).unwrap_or("unknown");
    let authority_gate = payload.get("rust_authority_gate").cloned().unwrap_or_else(|| json!({}));
    let authority_block = authority_gate.get("should_block").and_then(Value::as_bool).unwrap_or(false)
        || sync_result.pointer("/authority/would_block").and_then(Value::as_bool).unwrap_or(false);

    if csv_changed && csv_path.is_empty() {
        errors.push(Diagnostic::error("apply_manifest_missing_csv_path", Some("paths.shaped_devices_csv".to_string()), "CSV output changed but shaped_devices_csv path is empty"));
    }
    if network_changed && network_path.is_empty() {
        errors.push(Diagnostic::error("apply_manifest_missing_network_path", Some("paths.network_json".to_string()), "Network output changed but network_json path is empty"));
    }
    if files_changed && backup_before_apply && backup_dir.is_empty() {
        warnings.push(Diagnostic::warning("apply_manifest_backup_dir_empty", Some("paths.backup_dir".to_string()), "backup_before_apply is enabled but backup_dir is empty"));
    }

    let write_allowed = !dry_run && files_changed && policy_write_allowed && !authority_block && errors.is_empty();
    let backup_required = write_allowed && backup_before_apply;
    let mark_pending_apply = write_allowed && files_changed;
    let apply_required = !dry_run
        && policy_apply_allowed
        && !authority_block
        && errors.is_empty()
        && ((auto_apply && files_changed) || (retry_failed && pending_apply) || mode == "force_apply");

    if backup_required {
        operations.push(json!({
            "op": "backup_live_files",
            "phase": "before_write",
            "required": true,
            "path": backup_dir,
            "reason": mode,
        }));
        trace.push(json!({"step": "backup", "decision": "required"}));
    } else if files_changed {
        trace.push(json!({"step": "backup", "decision": if backup_before_apply { "not_allowed" } else { "not_required_by_config" }}));
    }

    if csv_changed {
        operations.push(json!({
            "op": "write_file",
            "phase": "write",
            "file": "ShapedDevices.csv",
            "path": csv_path,
            "allowed_now": write_allowed,
            "current_sha256": sha256_text(current_csv),
            "proposed_sha256": sha256_text(proposed_csv),
            "bytes": proposed_csv.as_bytes().len(),
        }));
    }
    if network_changed {
        operations.push(json!({
            "op": "write_file",
            "phase": "write",
            "file": "network.json",
            "path": network_path,
            "allowed_now": write_allowed,
            "current_sha256": sha256_text(current_network),
            "proposed_sha256": sha256_text(proposed_network),
            "bytes": proposed_network.as_bytes().len(),
        }));
    }
    if mark_pending_apply {
        operations.push(json!({
            "op": "mark_pending_apply",
            "phase": "post_write_state",
            "path": state_path,
            "allowed_now": write_allowed,
        }));
    }
    if apply_required {
        operations.push(json!({
            "op": "run_libreqos_update",
            "phase": "apply",
            "allowed_now": true,
            "cmd": str_path(&config, &["libreqos", "cmd"], "/opt/libreqos/src/LibreQoS.py"),
            "working_dir": str_path(&config, &["libreqos", "working_dir"], "/opt/libreqos/src"),
            "reason": if mode == "force_apply" { "force_apply" } else if files_changed { "files_changed" } else { "retry_pending_failed_apply" },
        }));
    }

    let status = if dry_run {
        "preview_only"
    } else if authority_block {
        "blocked_by_authority_gate"
    } else if !policy_write_allowed {
        "blocked_by_policy"
    } else if !errors.is_empty() {
        "blocked_by_manifest_validation"
    } else if !files_changed && !apply_required {
        "no_changes"
    } else {
        "ready"
    };

    let hashes = json!({
        "current_csv": sha256_text(current_csv),
        "proposed_csv": sha256_text(proposed_csv),
        "current_network": sha256_text(current_network),
        "proposed_network": sha256_text(proposed_network),
    });
    let manifest_basis = json!({
        "version": "0.9.0",
        "mode": mode,
        "paths": paths.clone(),
        "hashes": hashes.clone(),
        "csv_changed": csv_changed,
        "network_changed": network_changed,
        "policy_write_allowed": policy_write_allowed,
        "policy_apply_allowed": policy_apply_allowed,
        "sync_verdict": sync_verdict,
        "authority_block": authority_block,
        "operations": operations.clone(),
    });
    let manifest_id = format!("apply-{}", &compact_hash(&manifest_basis)[..16]);

    let result = json!({
        "mode": "transaction_preview",
        "authoritative": false,
        "manifest_id": manifest_id,
        "status": status,
        "input_mode": mode,
        "dry_run": dry_run,
        "files_changed": files_changed,
        "csv_changed": csv_changed,
        "network_changed": network_changed,
        "write_allowed": write_allowed,
        "apply_required": apply_required,
        "backup_required": backup_required,
        "policy_write_allowed": policy_write_allowed,
        "policy_apply_allowed": policy_apply_allowed,
        "authority_block": authority_block,
        "sync_plan_verdict": sync_verdict,
        "hashes": hashes,
        "operations": operations,
        "operation_count": operations.len(),
        "trace": trace,
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creates_no_changes_manifest() {
        let (result, errors, _warnings) = build_apply_manifest_payload(&json!({
            "mode": "apply",
            "current_csv_text": "same",
            "proposed_csv_text": "same",
            "current_network_text": "{}",
            "proposed_network_text": "{}",
            "files_changed": false,
            "config": {"app": {"auto_apply": true}}
        }));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("no_changes"));
        assert_eq!(result.get("operation_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn creates_write_operations_for_changed_files() {
        let (result, errors, _warnings) = build_apply_manifest_payload(&json!({
            "mode": "apply",
            "current_csv_text": "a",
            "proposed_csv_text": "b",
            "current_network_text": "{}",
            "proposed_network_text": "{\"n\":1}",
            "files_changed": true,
            "csv_changed": true,
            "network_changed": true,
            "paths": {"shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv", "network_json": "/opt/libreqos/src/network.json", "runtime_state": "/opt/LQoSync/state/runtime_state.json"},
            "config": {"app": {"auto_apply": true, "backup_before_apply": false}, "libreqos": {"cmd": "/opt/libreqos/src/LibreQoS.py", "working_dir": "/opt/libreqos/src"}},
            "policy_decision": {"write_allowed": true, "apply_allowed": true}
        }));
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("ready"));
        assert!(result.get("operation_count").and_then(Value::as_u64).unwrap_or(0) >= 3);
    }

    #[test]
    fn respects_authority_block() {
        let (result, _errors, _warnings) = build_apply_manifest_payload(&json!({
            "mode": "apply",
            "current_csv_text": "a",
            "proposed_csv_text": "b",
            "files_changed": true,
            "csv_changed": true,
            "paths": {"shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv"},
            "rust_authority_gate": {"should_block": true},
            "policy_decision": {"write_allowed": true, "apply_allowed": true}
        }));
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked_by_authority_gate"));
        assert_eq!(result.get("write_allowed").and_then(Value::as_bool), Some(false));
    }
}
