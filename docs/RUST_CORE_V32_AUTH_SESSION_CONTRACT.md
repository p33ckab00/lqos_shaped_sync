# Rust Core v3.2 RouterOS Auth Session Contract

LQoSync `2.102.0-rc1` / `lqosync-core 3.2.0` adds the next RouterOS authentication bridge operation:

```text
build-routeros-auth-session-contract
```

## Purpose

v3.0 added the redacted authentication plan. v3.1 added an offline authentication handshake fixture. v3.2 now turns a successful fixture handshake into a redacted authenticated-session contract.

This is the missing safety layer before any future live Rust authenticated read adapter.

```text
router config
  -> redacted auth plan
  -> fixture auth handshake
  -> redacted session contract
  -> future authenticated read pilot
```

## Safety boundary

This operation does **not** open sockets, authenticate to MikroTik, emit credentials, store tokens, or replace Python collectors.

It always reports:

```text
connection_attempt_count = 0
authentication_attempt_count = 0
api_sentence_write_count = 0
api_reply_read_count = 0
full_rust_backend = false
```

## New config defaults

```json
{
  "rust_core": {
    "routeros_auth_session_pilot": false,
    "allow_rust_routeros_session_state": false,
    "routeros_session_authority": "contract_only"
  }
}
```

## API

```text
GET  /api/rust-core/routeros-auth-session-contract
POST /api/rust-core/routeros-auth-session-contract
```

Fixture example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-auth-session-contract \
  -H 'Content-Type: application/json' \
  -d '{
    "router": {"name":"R1", "address":"10.0.0.1", "username":"admin", "password":"secret"},
    "adapter":"fixture",
    "execute":true,
    "fixture_reply_words":["!done"]
  }'
```

Expected status:

```text
auth_session_contract_ready
```

Rejected auth fixture returns:

```text
auth_session_not_established
```

Live adapter attempts remain blocked:

```text
routeros_auth_session_live_adapter_not_implemented
```

## Why this matters

A future live Rust RouterOS collector must not just connect and authenticate. It must prove it has a valid, redacted, auditable session state before issuing read commands. This update defines that session-state contract without enabling live network authority.

## Backend status

Still not full Rust backend.

```text
Python = live WebUI, run_cycle, live RouterOS collectors, default apply authority
Rust   = safety core, transport prep, auth/session contracts, transaction gates
```
