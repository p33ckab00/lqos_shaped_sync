# Rust Core v4.9 Collector Authority Production Freeze Gate

`rust/lqosync-core = 4.9.0`  
`LQoSync VERSION = 2.119.0-rc1`

## Summary

v4.9 adds the final **non-mutating pre-production freeze gate** before any future Rust collector-authority production switch contract.

This is not the final full Rust backend yet. It freezes and verifies the promotion/cutover inputs while keeping Python authoritative.

```text
cutover ledger
+ production freeze gates
+ manual confirmation
+ maintenance window
+ operator acknowledgment
+ rollback path
+ Python fallback requirement
+ side-effect checks
→ production freeze gate
```

## New Rust operation

```text
build-collector-authority-production-freeze-gate
```

## New API endpoint

```text
GET  /api/rust-core/collector-authority-production-freeze-gate
POST /api/rust-core/collector-authority-production-freeze-gate
```

## Manual confirmation token

```text
CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE
```

## New config defaults

```json
"rust_core": {
  "collector_authority_production_freeze_gate_pilot": false,
  "allow_collector_authority_production_freeze_gate": false,
  "collector_authority_production_freeze_mode": "freeze_only",
  "collector_authority_production_freeze_require_cutover_ledger": true,
  "collector_authority_production_freeze_require_python_fallback": true,
  "collector_authority_production_freeze_require_manual_confirmation": true,
  "collector_authority_production_freeze_require_no_cleanup_apply": true,
  "collector_authority_production_freeze_require_rollback_path": true,
  "collector_authority_production_freeze_require_maintenance_window": true,
  "collector_authority_production_freeze_require_operator_ack": true,
  "collector_authority_production_freeze_max_shadow_age_seconds": 900
}
```

## Safety behavior

v4.9 remains fail-safe:

```text
No live RouterOS reads
No Rust collector production switch
No cleanup authority transfer
No generated file writes
No LibreQoS apply authority
Python collector fallback remains mandatory
Python backend is not removable yet
```

The result explicitly keeps:

```text
full_rust_backend = false
production_collector_authority_switched = false
collector_authority_production_switch_supported = false
collector_authority_production_switch_executed = false
python_backend_removable = false
rust_can_drive_cleanup = false
rust_can_drive_apply = false
rust_can_write_generated_files = false
```

## Status values

```text
collector_authority_production_freeze_gate_shadow_only
collector_authority_production_freeze_gate_review
collector_authority_production_freeze_gate_ready
blocked
```

## Meaning of this phase

v4.9 is the final pre-switch freeze gate for the collector-authority path. The next logical phase is v5.0: a production switch contract for collector authority.

Full Python backend removal is later than v5.0. To remove Python, Rust must also own the API/service engine, scheduler, run-cycle orchestration, collectors, circuit builder, sync engine, apply/journal/rollback authority, and process supervision.

## Validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected operation:

```text
build-collector-authority-production-freeze-gate
```
