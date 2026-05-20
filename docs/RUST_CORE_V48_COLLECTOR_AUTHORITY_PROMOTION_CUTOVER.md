# Rust Core v4.8 Collector Authority Promotion Cutover Ledger

`rust/lqosync-core = 4.8.0`  
`LQoSync VERSION = 2.118.0-rc1`

## Summary

v4.8 adds the non-mutating collector authority promotion cutover ledger.

It sits after v4.7 promotion commit planning and records a future cutover intent without executing it.

```text
promotion commit plan
+ cutover ledger gates
+ manual confirmation
+ Python fallback requirement
+ rollback path
+ side-effect checks
→ cutover ledger
```

## New Rust operation

```text
build-collector-authority-promotion-cutover-ledger
```

## New API endpoint

```text
GET  /api/rust-core/collector-authority-promotion-cutover-ledger
POST /api/rust-core/collector-authority-promotion-cutover-ledger
```

## Manual confirmation token

```text
CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER
```

If Rust needs to build the v4.7 prerequisite internally, the caller may also provide:

```json
{
  "collector_authority_promotion_commit_confirmation": "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN"
}
```

## New config defaults

```json
"rust_core": {
  "collector_authority_promotion_cutover_ledger_pilot": false,
  "allow_collector_authority_promotion_cutover_ledger": false,
  "collector_authority_promotion_cutover_mode": "ledger_only",
  "collector_authority_promotion_cutover_require_commit_plan": true,
  "collector_authority_promotion_cutover_require_python_fallback": true,
  "collector_authority_promotion_cutover_require_manual_confirmation": true,
  "collector_authority_promotion_cutover_require_no_cleanup_apply": true,
  "collector_authority_promotion_cutover_require_rollback_path": true,
  "collector_authority_promotion_cutover_max_shadow_age_seconds": 900
}
```

## Safety behavior

v4.8 remains fail-safe:

```text
No live RouterOS reads
No Rust collector promotion
No cleanup authority transfer
No generated file writes
No LibreQoS apply authority
Python collector fallback remains mandatory
```

The result explicitly keeps:

```text
full_rust_backend = false
production_collector_authority_switched = false
collector_authority_promotion_supported = false
collector_authority_promotion_executed = false
rust_can_drive_cleanup = false
rust_can_drive_apply = false
rust_can_write_generated_files = false
```

## Status values

```text
collector_authority_promotion_cutover_ledger_shadow_only
collector_authority_promotion_cutover_ledger_review
collector_authority_promotion_cutover_ledger_ready
blocked
```

## Run validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected operation:

```text
build-collector-authority-promotion-cutover-ledger
```
