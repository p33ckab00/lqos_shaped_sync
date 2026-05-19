# Rust Core v2.8 RouterOS Offline Session Pipeline

Rust Core v2.8 adds `run-routeros-offline-session`, an end-to-end offline RouterOS API session rehearsal.

## Status

This is still not a full Rust backend phase.

Python remains authoritative for live RouterOS reads and production `run_cycle` orchestration. Rust does not open MikroTik sockets, authenticate, or consume live credentials in this phase.

## What this phase proves

The Rust core can now compose these previously separate layers into a single deterministic pipeline:

1. RouterOS API sentence builder
2. RouterOS API binary frame encoder
3. RouterOS API binary frame decoder
4. RouterOS API reply decoder
5. Sanitized fixture rows
6. Redacted diagnostics

The operation exists so a future live read-only socket adapter can plug into a tested protocol pipeline instead of inventing the framing and parsing flow at the same time as live networking.

## Operation

```text
run-routeros-offline-session
```

Example request:

```json
{
  "version": "1",
  "op": "run-routeros-offline-session",
  "payload": {
    "path": "/ppp/active",
    "fields": ["name", "address", "caller-id"],
    "fixture_rows": [
      {"name": "selftest", "address": "10.0.0.2", "caller-id": "AA:BB:CC:DD:EE:FF"}
    ]
  }
}
```

Expected result:

```text
status=offline_session_complete
connection_attempt_count=0
live_transport_supported=false
full_rust_backend=false
```

## API endpoint

```text
GET  /api/rust-core/routeros-offline-session
POST /api/rust-core/routeros-offline-session
```

## Redaction

Sensitive fixture keys are removed before reply words are generated:

```text
password
secret
token
key
api-key
```

The result reports only counts and redaction flags.

## Next stage

The next logical phase is a guarded read-only socket adapter pilot. That future stage must remain opt-in and should use the same pipeline introduced here.
