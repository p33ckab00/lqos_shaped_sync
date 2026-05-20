# Rust Core v4.4 Collector Authority Pilot Result Evaluator

Version: `2.114.0-rc1`  
Rust core: `lqosync-core 4.4.0`

## Purpose

v4.4 adds a non-mutating evaluator for a future Rust collector authority pilot result.

It sits after:

```text
v4.0 activation plan
v4.1 runtime contract
v4.2 switch rehearsal
v4.3 pilot execution contract
```

and evaluates whether the observed pilot result is clean enough to continue toward future handoff stages.

## New operation

```text
evaluate-collector-authority-pilot-result
```

## What it checks

The evaluator checks:

```text
pilot execution contract readiness
Python fallback requirement
pilot observation status
pilot error count
parity status
shadow freshness
cleanup/apply/write side-effect attempts
production authority switch attempts
```

## Status values

```text
collector_authority_pilot_result_shadow_only
collector_authority_pilot_result_review
collector_authority_pilot_result_pass
blocked
```

## Safety model

v4.4 is still fail-safe and non-mutating.

```text
No live RouterOS reads
No collector authority switch
No cleanup authority transfer
No generated file writes
No LibreQoS apply authority
Python collectors remain authoritative
```

The result explicitly keeps:

```text
full_rust_backend = false
production_collector_authority_switched = false
collector_authority_switch_executed = false
rust_can_drive_cleanup = false
rust_can_drive_apply = false
rust_can_write_generated_files = false
```

## API endpoint

```text
GET  /api/rust-core/collector-authority-pilot-result
POST /api/rust-core/collector-authority-pilot-result
```

Example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/collector-authority-pilot-result \
  -H 'Content-Type: application/json' \
  -d '{
    "shadow_age_seconds": 30,
    "pilot_result": {
      "status": "pilot_shadow_complete",
      "cleanup_attempted": false,
      "apply_attempted": false,
      "write_attempted": false,
      "error_count": 0
    },
    "collector_parity": {
      "verdict": "parity_pass",
      "parity_score": 100.0
    }
  }'
```

## Config defaults

```json
"rust_core": {
  "collector_authority_pilot_result_evaluator_pilot": false,
  "allow_collector_authority_pilot_result_evaluation": false,
  "collector_authority_pilot_result_mode": "evaluate_only",
  "collector_authority_pilot_result_require_execution_contract": true,
  "collector_authority_pilot_result_require_python_fallback": true,
  "collector_authority_pilot_result_require_no_cleanup_apply": true,
  "collector_authority_pilot_result_require_parity": true,
  "collector_authority_pilot_result_max_shadow_age_seconds": 900
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
evaluate-collector-authority-pilot-result
```
