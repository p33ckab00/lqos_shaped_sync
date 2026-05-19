# Rust Core v3.0 RouterOS Authentication Plan

LQoSync 2.100.0-rc1 / `lqosync-core` v3.0.0 adds a redacted RouterOS authentication planning layer.

## Operation

```text
build-routeros-auth-plan
```

## Purpose

This operation is a bridge between TCP reachability and a future live read-only Rust RouterOS API adapter. It validates that a selected router has enough connection and credential metadata for a future authentication step, but it never emits credential values and never authenticates.

## Safety default

```text
connection_attempt_count = 0
authentication_attempt_count = 0
api_sentence_write_count = 0
api_reply_read_count = 0
password_emitted = false
login_sentence_emitted = false
live_auth_supported = false
full_rust_backend = false
```

Python collectors remain authoritative.

## New config defaults

```json
"rust_core": {
  "routeros_auth_pilot": false,
  "routeros_auth_timeout_seconds": 5,
  "allow_rust_routeros_credentials": false,
  "routeros_transport_authority": "plan_only"
}
```

Even with gates enabled, this release returns `routeros_auth_adapter_not_implemented` for execution. It is a redacted plan only.

## API

```text
GET  /api/rust-core/routeros-auth-plan
POST /api/rust-core/routeros-auth-plan
```

Example:

```bash
curl "http://YOUR-LQOSYNC/api/rust-core/routeros-auth-plan?router=RB5k9-Distro"
```

## Not full Rust backend yet

This is still the RouterOS transport/authentication bridge phase:

```text
Python = live RouterOS collectors and run_cycle authority
Rust = safety core + transport/auth planning
```
