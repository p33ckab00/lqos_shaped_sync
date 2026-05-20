# Rust Core v5.7 Rust Sync Engine Authority Handoff Contract

`VERSION = 2.127.0-rc1`  
`rust/lqosync-core = 5.7.0`

## Summary

v5.7 adds the Rust sync engine authority handoff contract.

This phase moves the full-Rust-backend track after v5.6 circuit builder authority and prepares Rust to eventually own sync plan generation, diff evaluation, apply-manifest preview, and cleanup safety decisions.

## New operation

```text
build-rust-sync-engine-authority-handoff-contract
```

## New endpoint

```text
GET  /api/rust-core/rust-sync-engine-authority-handoff-contract
POST /api/rust-core/rust-sync-engine-authority-handoff-contract
```

## Required confirmation token

```text
CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT
```

## What it verifies

```text
circuit builder authority handoff readiness
sync plan shadow readiness
sync diff parity
apply-manifest preview readiness
cleanup safety verification
Python fallback requirement
manual confirmation
no side effects
```

## Safety behavior

v5.7 remains non-mutating:

```text
No Python backend removal
No Python sync engine replacement
No Rust sync engine authority switch
No ShapedDevices live write
No config/state write
No LibreQoS apply authority
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

## Config defaults

```json
"rust_core": {
  "rust_sync_engine_authority_handoff_contract_pilot": false,
  "allow_rust_sync_engine_authority_handoff_contract": false,
  "rust_sync_engine_authority_handoff_mode": "contract_only",
  "rust_sync_engine_authority_handoff_require_circuit_builder_authority": true,
  "rust_sync_engine_authority_handoff_require_python_fallback": true,
  "rust_sync_engine_authority_handoff_require_manual_confirmation": true,
  "rust_sync_engine_authority_handoff_require_sync_plan_shadow": true,
  "rust_sync_engine_authority_handoff_require_diff_parity": true,
  "rust_sync_engine_authority_handoff_require_apply_manifest_preview": true,
  "rust_sync_engine_authority_handoff_require_cleanup_safety": true,
  "rust_sync_engine_authority_handoff_require_no_side_effects": true,
  "rust_sync_engine_authority_handoff_max_shadow_age_seconds": 900
}
```

## Expected validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected operation:

```text
build-rust-sync-engine-authority-handoff-contract
```
