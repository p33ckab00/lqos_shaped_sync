# Rust Core v7.3.3 Steady-State Guard Hotfix

`rust/lqosync-core = 7.3.3`  
`LQoSync VERSION = 2.143.3-rc1`

## Summary

v7.3.3 fixes the aggregate `self-test` fixture for `build-full-rust-backend-steady-state-guard`.

## Root cause

The steady-state guard reads all three WebUI preservation gates directly from the top-level payload:

```text
webui_ux_unchanged
webui_static_asset_paths_unchanged
webui_static_assets_preserved
```

v7.3.2 added static asset gates, but the aggregate self-test `steady_state_payload` still missed the top-level `webui_ux_unchanged` gate. Because `bool_value(..., false)` defaulted to `false`, the steady-state guard correctly refused to report verified.

## Fix

The self-test steady-state payload now explicitly inserts:

```rust
obj.insert("webui_ux_unchanged".to_string(), json!(true));
obj.insert("webui_static_asset_paths_unchanged".to_string(), json!(true));
obj.insert("webui_static_assets_preserved".to_string(), json!(true));
```

## Safety behavior

Unchanged. The guard still requires:

```text
Rust backend production authority verified
Python backend retired with no drift
WebUI/UX/static assets preserved
Rollback package available
Rollback test passed
Server health checks passed
```
