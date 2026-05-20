# Rust Core v7.3.2 Steady-State Guard Self-Test Hotfix

`VERSION = 2.143.2-rc1`  
`lqosync-core = 7.3.2`

## Summary

v7.3.1 still failed the aggregate Rust core self-test at `self_test_full_rust_backend_steady_state_guard_failed`.

The standalone steady-state guard test passed, but the aggregate `self-test` payload still did not include the full WebUI/static-assets gate set required by the guard.

## Root cause

The steady-state guard requires all three WebUI preservation fields to be true:

```text
webui_ux_unchanged = true
webui_static_asset_paths_unchanged = true
webui_static_assets_preserved = true
```

v7.3.1 added `webui_static_assets_preserved`, but the aggregate steady-state self-test payload still lacked `webui_static_asset_paths_unchanged` at the final steady-state stage.

## Fix

The aggregate self-test steady-state payload now includes both:

```text
webui_static_asset_paths_unchanged = true
webui_static_assets_preserved = true
```

## Safety behavior

Unchanged:

```text
Rust backend remains production-authoritative only when gates pass
Python drift must remain absent
WebUI/UX/static assets must remain preserved
Rollback package must remain available
No blind service/file mutation by Rust self-test
```

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
build-full-rust-backend-steady-state-guard advertised
```
