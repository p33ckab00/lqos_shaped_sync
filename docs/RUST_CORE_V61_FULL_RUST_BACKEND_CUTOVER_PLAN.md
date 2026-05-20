# Rust Core v6.1 Full Rust Backend Cutover Plan

`rust/lqosync-core = 6.1.0`  
`LQoSync VERSION = 2.131.0-rc1`

## Summary

v6.1 adds the non-mutating full Rust backend cutover plan.

This phase comes after v6.0 full Rust backend production-readiness. It prepares the final operational cutover sequence while preserving the existing WebUI/UX and keeping Python backend fallback required.

## New Rust operation

```text
build-full-rust-backend-cutover-plan
```

## New API endpoint

```text
GET  /api/rust-core/full-rust-backend-cutover-plan
POST /api/rust-core/full-rust-backend-cutover-plan
```

## Manual confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_CUTOVER_PLAN
```

## What it verifies

```text
full Rust backend production-readiness contract
+ WebUI/UX unchanged guarantee
+ Python backend rollback path
+ operator cutover approval
+ Python fallback requirement
+ side-effect checks
↓
full Rust backend cutover plan
```

## Safety behavior

v6.1 remains non-mutating:

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

v6.1 can report:

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
```

## Why Python is not removed yet

Python removal must be a separate explicit package after server-side cargo tests pass and the Rust service can own live API/scheduler/run_cycle/apply authority.

Recommended next stage:

```text
v6.2 Python Backend Retirement / Rust Service Cutover Package
```
