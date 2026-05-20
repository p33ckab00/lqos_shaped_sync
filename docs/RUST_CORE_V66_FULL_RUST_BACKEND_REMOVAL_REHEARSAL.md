# Rust Core v6.6 Full Rust Backend Removal Rehearsal

`rust/lqosync-core = 6.6.0`  
`LQoSync VERSION = 2.136.0-rc1`

## Summary

v6.6 adds the final non-mutating rehearsal before a future v7.0 actual full Rust backend cutover / Python backend removal package.

It verifies the v6.5 Python backend removal execution contract, WebUI/UX unchanged guarantee, rollback path, operator acknowledgment, Python fallback requirement, and side-effect-free state.

## New Rust operation

```text
build-full-rust-backend-removal-rehearsal
```

## Required confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_REMOVAL_REHEARSAL
```

## New endpoint

```text
GET  /api/rust-core/full-rust-backend-removal-rehearsal
POST /api/rust-core/full-rust-backend-removal-rehearsal
```

## Safety behavior

v6.6 remains non-mutating:

```text
No Python backend removal
No Flask route disable
No API traffic switch to Rust
No Rust production service authority enablement
No generated file writes
No LibreQoS apply authority
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

It can mark:

```text
full_rust_backend_candidate = true
python_backend_removal_candidate = true
```

But it still keeps:

```text
full_rust_backend = false
full_rust_backend_production_enabled = false
python_backend_removed = false
python_backend_removable = false
python_removal_allowed = false
python_removal_executed = false
flask_routes_disabled = false
api_traffic_switched_to_rust = false
rust_service_runtime_authoritative = false
```

## Next stage

```text
v7.0 Actual Full Rust Backend Cutover / Python Backend Removal
```

v7.0 must be the explicit mutating package that can disable Python/Flask and switch API traffic only after server cargo tests, rollback rehearsal, and operator approval pass.

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
build-full-rust-backend-removal-rehearsal
```
