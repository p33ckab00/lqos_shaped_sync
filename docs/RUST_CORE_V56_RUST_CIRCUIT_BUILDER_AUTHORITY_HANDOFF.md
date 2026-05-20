# Rust Core v5.6 Rust Circuit Builder Authority Handoff Contract

`rust/lqosync-core = 5.6.0`  
`LQoSync VERSION = 2.126.0-rc1`

## Summary

v5.6 adds `build-rust-circuit-builder-authority-handoff-contract`.

This phase moves the full-Rust-backend track from live collector authority toward circuit row / ShapedDevices builder authority. It keeps WebUI/UX unchanged and keeps Python as the authoritative fallback.

## Current phase

```text
Full-Rust-backend track: circuit builder authority handoff stage
Final production: not yet
Python removal: not yet
WebUI/UX: unchanged
```

## New operation

```text
build-rust-circuit-builder-authority-handoff-contract
```

## Required confirmation token

```text
CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT
```

## What it checks

```text
live collector authority handoff readiness
circuit builder shadow output
ShapedDevices render parity
parent-node integrity
Python backend fallback requirement
manual confirmation
side-effect-free state
```

## Safety behavior

v5.6 remains non-mutating:

```text
No Python backend removal
No Python circuit builder replacement
No Rust circuit builder authority switch
No ShapedDevices live write
No config/state write
No LibreQoS apply authority
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

## API endpoint

```text
GET  /api/rust-core/rust-circuit-builder-authority-handoff-contract
POST /api/rust-core/rust-circuit-builder-authority-handoff-contract
```

## Config defaults

```json
"rust_core": {
  "rust_circuit_builder_authority_handoff_contract_pilot": false,
  "allow_rust_circuit_builder_authority_handoff_contract": false,
  "rust_circuit_builder_authority_handoff_mode": "contract_only",
  "rust_circuit_builder_authority_handoff_require_live_collector_authority": true,
  "rust_circuit_builder_authority_handoff_require_python_fallback": true,
  "rust_circuit_builder_authority_handoff_require_manual_confirmation": true,
  "rust_circuit_builder_authority_handoff_require_circuit_shadow": true,
  "rust_circuit_builder_authority_handoff_require_shaped_devices_parity": true,
  "rust_circuit_builder_authority_handoff_require_parent_integrity": true,
  "rust_circuit_builder_authority_handoff_require_no_side_effects": true,
  "rust_circuit_builder_authority_handoff_max_shadow_age_seconds": 900
}
```

## Server validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected operation:

```text
build-rust-circuit-builder-authority-handoff-contract
```
