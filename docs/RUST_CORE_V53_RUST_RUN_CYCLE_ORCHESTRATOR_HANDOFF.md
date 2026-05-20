# Rust Core v5.3 Rust Run Cycle Orchestrator Handoff Contract

LQoSync `2.123.0-rc1` / `lqosync-core 5.3.0` adds the Rust run_cycle orchestrator handoff contract.

## Current phase

```text
v5.3 = Rust run_cycle orchestrator handoff contract
Full Rust backend production = not yet
Python removal = not yet
WebUI/UX = unchanged
```

## New operation

```text
build-rust-run-cycle-orchestrator-handoff-contract
```

## Purpose

v5.3 sits after v5.2 scheduler/run_cycle handoff planning. It verifies whether Rust can own the future run_cycle orchestration graph while Python remains the active authority.

It checks:

```text
scheduler handoff readiness
run_cycle orchestrator manifest readiness
run_cycle shadow cycle success
config/state shadow verification
Python fallback requirement
manual confirmation
no side effects
```

Required confirmation token:

```text
CONFIRM_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT
```

## Safety behavior

Still non-mutating:

```text
No Python backend removal
No Python run_cycle replacement
No Rust run_cycle authority switch
No cleanup authority transfer
No generated file writes
No LibreQoS apply authority
WebUI/UX remains unchanged
Python backend fallback remains mandatory
```

## API endpoint

```text
GET  /api/rust-core/rust-run-cycle-orchestrator-handoff-contract
POST /api/rust-core/rust-run-cycle-orchestrator-handoff-contract
```

## Config defaults

```json
"rust_core": {
  "rust_run_cycle_orchestrator_handoff_contract_pilot": false,
  "allow_rust_run_cycle_orchestrator_handoff_contract": false,
  "rust_run_cycle_orchestrator_handoff_mode": "contract_only",
  "rust_run_cycle_orchestrator_handoff_require_scheduler_handoff": true,
  "rust_run_cycle_orchestrator_handoff_require_python_fallback": true,
  "rust_run_cycle_orchestrator_handoff_require_manual_confirmation": true,
  "rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow": true,
  "rust_run_cycle_orchestrator_handoff_require_config_state_shadow": true,
  "rust_run_cycle_orchestrator_handoff_require_no_side_effects": true,
  "rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds": 900
}
```

## Next stage

```text
v5.4 Rust config/state authority handoff contract
```
