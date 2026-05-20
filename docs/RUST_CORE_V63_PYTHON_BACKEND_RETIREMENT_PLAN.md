# Rust Core v6.3 Python Backend Retirement Plan

`rust/lqosync-core = 6.3.0`  
`LQoSync VERSION = 2.133.0-rc1`

## Summary

v6.3 adds the first explicit Python backend retirement planning gate after the v6.2 full Rust backend cutover execution contract.

This is still **not** the actual Python removal package. It plans retirement while keeping Python fallback available and WebUI/UX unchanged.

## New Rust operation

```text
build-python-backend-retirement-plan
```

## New API endpoint

```text
GET  /api/rust-core/python-backend-retirement-plan
POST /api/rust-core/python-backend-retirement-plan
```

## Required confirmation token

```text
CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN
```

## What it checks

```text
full Rust backend cutover execution contract
+ WebUI/UX unchanged guarantee
+ Python rollback path
+ operator retirement acknowledgment
+ Python fallback requirement
+ no side-effect checks
↓
Python backend retirement plan
```

## Safety behavior

v6.3 is non-mutating:

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

## Important flags

v6.3 can mark:

```text
full_rust_backend_candidate = true
python_backend_retirement_candidate = true
```

But it still keeps:

```text
full_rust_backend = false
full_rust_backend_production_enabled = false
python_backend_removed = false
python_backend_removable = false
python_removal_allowed = false
flask_routes_disabled = false
api_traffic_switched_to_rust = false
rust_service_runtime_authoritative = false
```

## New config defaults

```json
"rust_core": {
  "python_backend_retirement_plan_pilot": false,
  "allow_python_backend_retirement_plan": false,
  "python_backend_retirement_mode": "plan_only",
  "python_backend_retirement_require_cutover_execution_contract": true,
  "python_backend_retirement_require_python_fallback": true,
  "python_backend_retirement_require_manual_confirmation": true,
  "python_backend_retirement_require_webui_unchanged": true,
  "python_backend_retirement_require_rollback_path": true,
  "python_backend_retirement_require_operator_ack": true,
  "python_backend_retirement_require_no_side_effects": true,
  "python_backend_retirement_max_shadow_age_seconds": 900
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
build-python-backend-retirement-plan
```
