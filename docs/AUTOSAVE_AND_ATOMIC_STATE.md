# Autosave and Atomic State Model

LQoSync should preserve the existing no-save-button operator model while making every write safer.

```text
User edits a field
  ↓
UI shows Saving...
  ↓
Python receives a PATCH request
  ↓
Rust validates the proposed change
  ↓
Rust writes atomically if safe
  ↓
UI shows Saved or Blocked
```

## Autosave goals

```text
- No manual Save button for normal fields.
- Field-level changes are validated before write.
- Dangerous changes require confirmation.
- Every accepted write is atomic.
- Every accepted write is auditable.
- Rollback is possible from previous versions/backups.
```

## Recommended UI states

```text
Saving...
Saved
Blocked
Needs attention
Validation warning
```

## Recommended endpoints

```text
PATCH /api/config/field
PATCH /api/policy/field
PATCH /api/router/field
PATCH /api/topology/field
```

Example request:

```json
{
  "path": "policies.cleanup_sources.dhcp.normal_inactive_action",
  "value": "cleanup_immediate"
}
```

Example response:

```json
{
  "ok": true,
  "saved": true,
  "mode": "custom",
  "message": "Saved",
  "warnings": []
}
```

Blocked response:

```json
{
  "ok": false,
  "saved": false,
  "error": "invalid_policy_action",
  "message": "cleanup_now is not a valid cleanup action"
}
```

## Debounce guidance

| Field type | Behavior |
|---|---|
| Text input | Autosave after 600–1000ms of no typing. |
| Number input | Autosave after 600–1000ms and validate range. |
| Dropdown | Autosave immediately. |
| Toggle | Autosave immediately. |
| Dangerous field | Confirmation modal first, then autosave. |
| Topology drag/drop | Draft autosave first; commit only when validation is safe. |

## Dangerous changes

These changes should require confirmation before Rust writes them:

```text
- enabling auto_apply
- disabling backup_before_apply when auto_apply is enabled
- changing libreqos.working_dir
- changing ShapedDevices.csv path
- changing network.json path
- deleting a router
- disabling a source with active clients
- deleting topology nodes
- moving many clients by topology drag/drop
- switching cleanup policy to cleanup_immediate for active sources
- changing policy preset from conservative/balanced to aggressive
```

## Files that require atomic write

The Rust atomic state/file engine should own these files:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/LQoSync/state/runtime_state.json
/opt/LQoSync/state/policy_state.json
/opt/LQoSync/state/collector_cache.json
/opt/LQoSync/logs/audit.jsonl
```

`collector_cache.json` is included because it may affect source trust and speed/source continuity in later cycles. A corrupt cache can produce bad decisions in the next sync cycle.

## Atomic write requirements

For normal JSON/CSV replacement:

```text
1. Serialize typed data.
2. Write to temporary file in same directory.
3. Flush file.
4. fsync file.
5. Rename temp file over target.
6. fsync parent directory where supported.
7. Verify checksum when enabled.
8. Emit audit event.
```

For `audit.jsonl` append:

```text
1. Open append-only.
2. Write one complete JSON line.
3. Flush.
4. fsync based on configured durability level.
```

## Backup and rollback

Every autosave does not need a full LibreQoS backup ZIP, but it should have enough rollback metadata for critical files.

Recommended:

```text
- config versions: keep last 30
- policy_state versions: keep last 30
- network/topology versions: keep last 30 or include in normal backup manifest
- audit all changes
- show old/new value for field-level config changes
```

Example audit event:

```json
{
  "event": "config_autosaved",
  "path": "policies.cleanup_sources.dhcp.normal_inactive_action",
  "old": "cleanup_next_run",
  "new": "cleanup_immediate",
  "actor": "admin",
  "result": "saved"
}
```

## Policy mode behavior

Manual policy edits should automatically move the policy state to custom mode:

```text
policies.mode = custom
```

The UI should show:

```text
Saved · Custom policy
```

## Topology autosave behavior

Topology changes are more dangerous than normal form fields.

Recommended behavior:

```text
1. Save UI draft locally or to draft state.
2. Validate topology through Rust.
3. If safe, atomically commit network.json.
4. If risky, hold as draft and require confirmation.
```

This prevents one drag/drop action from silently moving many active subscribers into a bad LibreQoS parent node.

## Current package status

This package adds the Rust protocol, parser, validator scaffold, and optional
Python wrapper. Full Rust atomic writing is still a later phase.

The following config section is now normalized by Python:

```json
{
  "rust_core": {
    "enabled": true,
    "binary_path": "",
    "timeout_seconds": 10,
    "enforce_validation": false,
    "prefer_daemon": false,
    "unix_socket": "/run/lqosync-core.sock"
  }
}
```

Early safety behavior:

```text
- Rust validation is visible in Dry Run when the binary is available.
- Python fallback remains active when the binary is missing.
- enforce_validation is false by default to avoid blocking existing installs.
- Later v0.3 work should move config/state/cache/file writes into Rust.
```
