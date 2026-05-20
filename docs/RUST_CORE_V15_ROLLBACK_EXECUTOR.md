# Rust Core v1.5 Rollback Execution Rehearsal

Rust Core v1.5 adds the `execute-rollback` protocol operation. It is designed as the controlled counterpart to v1.4 transaction history and rollback-plan viewing.

## Purpose

The rollback executor can rehearse a rollback plan and, only when explicitly enabled, restore text-based generated files from backup paths recorded in a rollback manifest.

## Default safety

Rollback execution is disabled by default. The operation defaults to rehearsal mode and does not restore files unless all of these are true:

```text
execute=true
allow_rollback_file_writes=true
confirmation=CONFIRM_ROLLBACK
mode != dry_run
rollback_manifest.status=rollback_available
```

The Python WebUI/orchestrator remains authoritative by default. The Python fallback never restores files.

## New protocol operation

```json
{
  "version": "1",
  "op": "execute-rollback",
  "payload": {
    "journal_id": "txj-example",
    "execute": false,
    "confirmation": ""
  }
}
```

The Rust core can resolve rollback input from one of these sources:

```text
rollback_manifest
journal_id
manifest_id
embedded transaction/apply context
```

## New config flags

```json
"rust_core": {
  "execute_rollback": false,
  "allow_rust_rollback_file_writes": false,
  "rollback_authority": "preview"
}
```

To allow real file restores later, the operator must intentionally change:

```json
"rollback_authority": "execute_file_restores"
```

and send `confirmation=CONFIRM_ROLLBACK` in the request.

## API endpoint

```text
POST /api/rust-core/rollback-execute
```

Example rehearsal request:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/rollback-execute \
  -H 'Content-Type: application/json' \
  -d '{"journal_id":"txj-example","execute":false}'
```

Example explicit execution request, only after enabling the config flags:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/rollback-execute \
  -H 'Content-Type: application/json' \
  -d '{"journal_id":"txj-example","execute":true,"confirmation":"CONFIRM_ROLLBACK"}'
```

## What gets restored

The rollback manifest must contain operations like:

```json
{
  "op": "restore_file",
  "target_path": "/opt/libreqos/src/ShapedDevices.csv",
  "backup_path": "/opt/LQoSync/backups/.../ShapedDevices.csv",
  "expected_current_sha256": "...",
  "restore_sha256": "..."
}
```

The executor checks backup existence, backup checksum, and target checksum before restore unless `allow_checksum_mismatch=true` is explicitly supplied.

## Status values

```text
rehearsal_only
confirmation_required
dry_run_preview_only
not_ready
no_restore_operations
executed_file_restores
failed
```

## Important limitation

v1.5 does not roll back external LibreQoS runtime state and does not run LibreQoS.py. It only rehearses or restores files recorded in the rollback manifest.
