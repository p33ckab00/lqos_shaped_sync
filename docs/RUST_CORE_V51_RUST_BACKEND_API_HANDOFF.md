# Rust Core v5.1 Rust Backend API Handoff Plan

`rust/lqosync-core = 5.1.0`  
`LQoSync VERSION = 2.121.0-rc1`

## Summary

v5.1 starts the **full Rust backend** track after v5.0 collector-authority production switch contract.

This phase does **not** remove Python yet. Instead, it prepares a route-parity/API handoff plan so the existing WebUI/UX can remain visually unchanged while a future Rust API/service layer replaces the Python/Flask backend.

## New Rust operation

```text
build-rust-backend-api-handoff-plan
```

## New API endpoint

```text
GET  /api/rust-core/rust-backend-api-handoff-plan
POST /api/rust-core/rust-backend-api-handoff-plan
```

## Required confirmation token

```text
CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN
```

## What it checks

```text
production switch contract readiness
WebUI/UX unchanged flag
static asset compatibility flag
API route parity inventory
Python backend fallback requirement
manual confirmation
side-effect-free status
```

## Safety behavior

v5.1 remains non-mutating:

```text
No Python removal
No Flask route replacement
No API traffic switch to Rust
No cleanup authority transfer
No generated file writes
No LibreQoS apply authority
```

The result explicitly keeps:

```text
full_rust_backend = false
python_backend_removable = false
python_backend_removed = false
python_backend_required = true
python_backend_fallback_required = true
rust_api_service_authoritative = false
rust_scheduler_authoritative = false
rust_run_cycle_authoritative = false
rust_apply_authoritative = false
```

## New config defaults

```json
"rust_core": {
  "rust_backend_api_handoff_plan_pilot": false,
  "allow_rust_backend_api_handoff_plan": false,
  "rust_backend_api_handoff_mode": "plan_only",
  "rust_backend_api_handoff_require_production_switch_contract": true,
  "rust_backend_api_handoff_require_python_backend_fallback": true,
  "rust_backend_api_handoff_require_manual_confirmation": true,
  "rust_backend_api_handoff_require_webui_compatibility": true,
  "rust_backend_api_handoff_require_route_parity": true,
  "rust_backend_api_handoff_require_no_side_effects": true,
  "rust_backend_api_handoff_max_shadow_age_seconds": 900
}
```

## Why Python is not removed in v5.1

The WebUI can stay as-is visually, but the Python backend cannot be removed until Rust owns the service/API layer, scheduler, run_cycle orchestrator, live collectors, sync engine, config/state/audit writes, and apply/journal/rollback authority.

v5.1 only starts that backend handoff path.
