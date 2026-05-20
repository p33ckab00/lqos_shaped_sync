# Rust Core v6.5 Python Backend Removal Execution Contract

`rust/lqosync-core = 6.5.0`  
`LQoSync VERSION = 2.135.0-rc1`

## Summary

v6.5 adds the first explicit Python backend removal execution contract.

This is still a safety-gated, non-mutating contract. It can declare that Python backend removal is a candidate for a later explicit cutover/removal package, but it does not remove Python, disable Flask routes, switch API traffic, or enable Rust service authority.

## New Rust operation

```text
build-python-backend-removal-execution-contract
```

## New API endpoint

```text
GET  /api/rust-core/python-backend-removal-execution-contract
POST /api/rust-core/python-backend-removal-execution-contract
```

## Manual confirmation token

```text
CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION_CONTRACT
```

## New config defaults

```json
"rust_core": {
  "python_backend_removal_execution_contract_pilot": false,
  "allow_python_backend_removal_execution_contract": false,
  "python_backend_removal_execution_mode": "contract_only",
  "python_backend_removal_execution_require_rust_enablement_contract": true,
  "python_backend_removal_execution_require_python_fallback": true,
  "python_backend_removal_execution_require_manual_confirmation": true,
  "python_backend_removal_execution_require_webui_unchanged": true,
  "python_backend_removal_execution_require_rollback_path": true,
  "python_backend_removal_execution_require_operator_ack": true,
  "python_backend_removal_execution_require_no_side_effects": true,
  "python_backend_removal_execution_max_shadow_age_seconds": 900
}
```

## Safety behavior

v6.5 remains non-mutating:

```text
No Python backend removal
No Flask route disable
No API traffic switch to Rust
No Rust service runtime authority enablement
No generated file writes
No LibreQoS apply authority
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

It can mark:

```text
python_backend_removal_candidate = true
full_rust_backend_candidate = true
```

But it still keeps:

```text
python_backend_removed = false
python_backend_removable = false
python_removal_allowed = false
python_removal_executed = false
flask_routes_disabled = false
api_traffic_switched_to_rust = false
rust_service_runtime_authoritative = false
```

## Phase meaning

v6.5 is very close to final production, but it is not the package that removes Python. The next safe step should be a server-tested full Rust backend removal rehearsal or final cutover/removal package with verified rollback.
