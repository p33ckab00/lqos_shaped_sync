# Rust Core v6.0 Full Rust Backend Production Readiness Contract

`rust/lqosync-core = 6.0.0`  
`LQoSync VERSION = 2.130.0-rc1`

## Summary

v6.0 adds the first full Rust backend production-readiness contract.

This phase sits after v5.9 service/API runtime handoff and checks whether all backend authority areas have reached a ready state for a future production cutover.

It still does **not** remove Python or switch live API/service traffic.

## New Rust operation

```text
build-full-rust-backend-production-readiness-contract
```

## New API endpoint

```text
GET  /api/rust-core/full-rust-backend-production-readiness-contract
POST /api/rust-core/full-rust-backend-production-readiness-contract
```

## Required confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT
```

## What it checks

```text
Rust backend service/runtime handoff readiness
WebUI/UX unchanged guarantee
operator final review acknowledgement
Python fallback requirement
no side-effect guarantee
shadow freshness
```

## Important production note

v6.0 can mark the system as a **full Rust backend cutover candidate**, but it does not execute the cutover.

Python remains required as fallback until a later explicit Python-retirement/cutover package passes server cargo tests and runtime validation.

## Safety behavior

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

## New config defaults

```json
"rust_core": {
  "full_rust_backend_production_readiness_contract_pilot": false,
  "allow_full_rust_backend_production_readiness_contract": false,
  "full_rust_backend_production_readiness_mode": "contract_only",
  "full_rust_backend_production_readiness_require_service_runtime": true,
  "full_rust_backend_production_readiness_require_python_fallback": true,
  "full_rust_backend_production_readiness_require_manual_confirmation": true,
  "full_rust_backend_production_readiness_require_webui_unchanged": true,
  "full_rust_backend_production_readiness_require_operator_final_review": true,
  "full_rust_backend_production_readiness_require_no_side_effects": true,
  "full_rust_backend_production_readiness_max_shadow_age_seconds": 900
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
build-full-rust-backend-production-readiness-contract
```
