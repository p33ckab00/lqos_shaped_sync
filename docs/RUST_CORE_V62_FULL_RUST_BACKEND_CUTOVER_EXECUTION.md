# Rust Core v6.2 Full Rust Backend Cutover Execution Contract

`rust/lqosync-core = 6.2.0`  
`LQoSync VERSION = 2.132.0-rc1`

## Summary

v6.2 adds the full Rust backend cutover execution contract.

This phase comes after v6.1 cutover planning. It verifies that the system is ready for a future execution package, but it is still non-mutating.

```text
full Rust backend cutover plan
+ execution contract gates
+ WebUI/UX unchanged guarantee
+ Python rollback path
+ operator execution acknowledgment
+ Python fallback requirement
+ side-effect checks
→ full Rust backend cutover execution contract
```

## New Rust operation

```text
build-full-rust-backend-cutover-execution-contract
```

## Manual confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_CUTOVER_EXECUTION_CONTRACT
```

## Important safety behavior

v6.2 does **not** remove Python and does **not** switch API traffic to Rust.

It explicitly keeps:

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

## New endpoint

```text
GET  /api/rust-core/full-rust-backend-cutover-execution-contract
POST /api/rust-core/full-rust-backend-cutover-execution-contract
```

## New config defaults

```json
"rust_core": {
  "full_rust_backend_cutover_execution_contract_pilot": false,
  "allow_full_rust_backend_cutover_execution_contract": false,
  "full_rust_backend_cutover_execution_mode": "contract_only",
  "full_rust_backend_cutover_execution_require_cutover_plan": true,
  "full_rust_backend_cutover_execution_require_python_fallback": true,
  "full_rust_backend_cutover_execution_require_manual_confirmation": true,
  "full_rust_backend_cutover_execution_require_webui_unchanged": true,
  "full_rust_backend_cutover_execution_require_rollback_path": true,
  "full_rust_backend_cutover_execution_require_operator_ack": true,
  "full_rust_backend_cutover_execution_require_no_side_effects": true,
  "full_rust_backend_cutover_execution_max_shadow_age_seconds": 900
}
```

## Production/removal note

v6.2 is near-final, but Python retirement still requires a later explicit package that can be reviewed separately. The WebUI/UX remains as-is; the backend route/service authority is the part being migrated.
