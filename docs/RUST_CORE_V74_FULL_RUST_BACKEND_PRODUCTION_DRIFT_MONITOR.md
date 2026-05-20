# Rust Core v7.4 Full Rust Backend Production Drift Monitor

`rust/lqosync-core = 7.4.0`  
`LQoSync VERSION = 2.144.0-rc1`

## Summary

v7.4 adds a post-steady-state production drift monitor for a fully migrated Rust backend.

It verifies that production remains in the intended Rust-authoritative state after Python retirement:

```text
steady-state guard passed
+ Rust runtime remains authoritative
+ API traffic remains on Rust
+ Python/Flask does not drift back into service
+ WebUI/UX/static assets remain unchanged
+ rollback package remains ready
+ server health checks pass
→ production drift monitor healthy
```

## New Rust operation

```text
build-full-rust-backend-production-drift-monitor
```

## New API endpoint

```text
GET  /api/rust-core/full-rust-backend-production-drift-monitor
POST /api/rust-core/full-rust-backend-production-drift-monitor
```

## Manual confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR
```

## New script

```text
scripts/full-rust-backend-production-drift-monitor.sh
```

Example:

```bash
export CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR=CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR
export PYTHON_BACKEND_PROCESS_COUNT=0
export DRIFT_CHECK_COUNT=1
sudo -E scripts/full-rust-backend-production-drift-monitor.sh
```

## New config defaults

```json
"rust_core": {
  "full_rust_backend_production_drift_monitor_pilot": false,
  "allow_full_rust_backend_production_drift_monitor": false,
  "full_rust_backend_production_drift_monitor_mode": "monitor_only",
  "full_rust_backend_drift_monitor_require_steady_state_guard": true,
  "full_rust_backend_drift_monitor_require_runtime_health": true,
  "full_rust_backend_drift_monitor_require_no_python_drift": true,
  "full_rust_backend_drift_monitor_require_webui_unchanged": true,
  "full_rust_backend_drift_monitor_require_rollback_package": true,
  "full_rust_backend_drift_monitor_require_server_tests": true,
  "full_rust_backend_drift_monitor_require_manual_confirmation": true,
  "full_rust_backend_drift_monitor_require_operator_ack": true,
  "full_rust_backend_drift_monitor_max_shadow_age_seconds": 900
}
```

## Safety behavior

v7.4 is verification-only:

```text
No service restarts
No Python file deletion
No Flask route mutation
No API traffic switching
No rollback execution
No generated LibreQoS writes
No LibreQoS apply authority
WebUI/UX/static assets remain preserved
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
build-full-rust-backend-production-drift-monitor
```
