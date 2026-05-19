# Rust Core v3.1 RouterOS Auth Handshake Fixture

LQoSync 2.101.0-rc1 / `lqosync-core` 3.1.0 adds `run-routeros-auth-handshake`.

This phase is **not full Rust backend**. It is the next safety bridge after the v3.0 authentication plan.

## Purpose

The operation models the future RouterOS authentication request/reply state machine using fixture replies only:

```text
router config
→ redacted auth plan
→ fixture login reply words
→ offline reply decoder
→ accepted / rejected / incomplete handshake result
```

## Safety guarantees

`run-routeros-auth-handshake` does not:

```text
open a TCP socket
authenticate to MikroTik
emit username/password values
send RouterOS API login words
replace Python collectors
```

The result always reports:

```text
connection_attempt_count = 0
authentication_attempt_count = 0
api_sentence_write_count = 0
api_reply_read_count = 0
full_rust_backend = false
```

## API

```text
GET  /api/rust-core/routeros-auth-handshake
POST /api/rust-core/routeros-auth-handshake
```

Example fixture acceptance:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-auth-handshake \
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
auth_fixture_accepted
```

A fixture trap returns:

```text
auth_fixture_rejected
```

A live adapter request remains blocked:

```text
routeros_auth_handshake_live_adapter_not_implemented
```

## Next stage

The next safe step is a heavily gated live read-only RouterOS authentication adapter pilot. That still should not replace Python collectors until parity and fallback behavior are proven.
