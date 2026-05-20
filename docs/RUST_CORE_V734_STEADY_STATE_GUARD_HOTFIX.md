# Rust Core v7.3.4 Steady-State Guard Hotfix

`rust/lqosync-core = 7.3.4`  
`LQoSync VERSION = 2.143.4-rc1`

## Summary

v7.3.4 fixes the aggregate self-test fixture for the full Rust backend steady-state guard.

The steady-state guard requires the rollback gate at the top-level payload:

```text
python_backend_rollback_package_ready = true
rollback_test_passed = true
rollback_path = restore_python_backend_and_flask_routes
```

v7.3.3 already supplied the WebUI gates, but the steady-state guard reads `python_backend_rollback_package_ready` directly and does not treat `python_fallback_backup_ready` as equivalent.

## Fix

`rust/lqosync-core/src/self_test.rs` now inserts:

```rust
obj.insert("python_backend_rollback_package_ready".to_string(), json!(true));
```

inside the `steady_state_payload` block.

## Safety

This is a test fixture correction only. It does not remove Python, disable Flask, switch API traffic, write generated files, or apply LibreQoS changes. WebUI/UX/static assets remain protected and rollback readiness remains required.

## Expected validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected:

```text
193 passed
self-test ok
operation_count: 82
build-full-rust-backend-steady-state-guard advertised
```
