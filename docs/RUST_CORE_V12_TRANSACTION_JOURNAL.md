# Rust Core v1.2 Transaction Journal and Rollback Manifest

Rust Core v1.2 adds non-mutating transaction accountability for the `lqosync-in-rust` branch.

## New protocol operations

```text
build-transaction-journal
build-rollback-manifest
```

These operations do not write files by default. They create structured previews that can be shown in Dry Run, stored later as JSONL, or used by a future rollback executor.

## Why this exists

Before Rust is allowed to become the primary file-write path, every planned or executed transaction needs an auditable record:

```text
Rust sync plan
→ apply manifest
→ apply transaction rehearsal/execution
→ transaction journal entry
→ rollback manifest preview
```

This gives operators a concrete record of what would be written, what was written, whether backup restore points exist, and what restore operations would be required if rollback is needed.

## build-transaction-journal

Inputs:

```json
{
  "mode": "apply",
  "rust_apply_manifest": {},
  "rust_apply_transaction": {},
  "rust_sync_plan": {},
  "rust_authority_gate": {},
  "paths": {
    "transaction_journal": "/opt/LQoSync/logs/transaction_journal.jsonl"
  }
}
```

Output includes:

```text
journal_id
journal_path
append_required
append_executed=false
rollback_available
manifest_id
transaction_status
write_count
event
```

`append_executed` remains false in v1.2. The operation is a preview builder, not a journal writer.

## build-rollback-manifest

The rollback manifest inspects transaction `write_results` and looks for backup restore points. If backup paths exist, it creates preview operations like:

```json
{
  "op": "restore_file",
  "phase": "rollback",
  "target_path": "/opt/libreqos/src/ShapedDevices.csv",
  "backup_path": "/opt/libreqos/src/ShapedDevices.csv.bak",
  "allowed_now": false
}
```

Rollback execution is not implemented in v1.2. The manifest is preview-only and requires operator confirmation in future authority phases.

## Dry Run visibility

Dry Run now shows a **Rust Transaction Journal & Rollback Preview** card with:

```text
journal ID
append required
rollback status
restore operation count
full JSON details
```

## Safety defaults

```text
Python remains authoritative.
Rust journal is preview-only.
Rust rollback is preview-only.
No LibreQoS apply authority changes.
No file writes are added by this release.
```

## Canonical paths

```text
/opt/LQoSync/logs/transaction_journal.jsonl
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```
