# Rust Core v5.8 Rust Apply/Journal/Rollback Authority Handoff Contract

`VERSION = 2.128.0-rc1`  
`lqosync-core = 5.8.0`

## Current phase

```text
Rust apply/journal/rollback authority handoff contract
```

This phase is part of the full-Rust-backend track, but it is **not** full Rust backend production yet. Python backend fallback remains mandatory and the WebUI/UX remains unchanged.

## New operation

```text
build-rust-apply-journal-rollback-authority-handoff-contract
```

## Purpose

v5.8 prepares Rust to eventually own the final apply layer:

```text
apply transaction authority
transaction journal authority
rollback manifest authority
rollback executor authority
audit shadow authority
```

It checks shadow verification for apply, journal, rollback, and audit paths after v5.7 sync engine authority handoff.

## Required confirmation

```text
CONFIRM_RUST_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF_CONTRACT
```

## Safety behavior

Still non-mutating:

```text
No Python backend removal
No Rust apply authority switch
No Rust journal authority switch
No Rust rollback authority switch
No live ShapedDevices write
No LibreQoS apply
No journal append
No rollback execute
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

## New endpoint

```text
GET  /api/rust-core/rust-apply-journal-rollback-authority-handoff-contract
POST /api/rust-core/rust-apply-journal-rollback-authority-handoff-contract
```

## New config defaults

```json
"rust_core": {
  "rust_apply_journal_rollback_authority_handoff_contract_pilot": false,
  "allow_rust_apply_journal_rollback_authority_handoff_contract": false,
  "rust_apply_journal_rollback_authority_handoff_mode": "contract_only",
  "rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority": true,
  "rust_apply_journal_rollback_authority_handoff_require_python_fallback": true,
  "rust_apply_journal_rollback_authority_handoff_require_manual_confirmation": true,
  "rust_apply_journal_rollback_authority_handoff_require_apply_shadow": true,
  "rust_apply_journal_rollback_authority_handoff_require_journal_shadow": true,
  "rust_apply_journal_rollback_authority_handoff_require_rollback_shadow": true,
  "rust_apply_journal_rollback_authority_handoff_require_audit_shadow": true,
  "rust_apply_journal_rollback_authority_handoff_require_no_side_effects": true,
  "rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds": 900
}
```

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
build-rust-apply-journal-rollback-authority-handoff-contract
```
