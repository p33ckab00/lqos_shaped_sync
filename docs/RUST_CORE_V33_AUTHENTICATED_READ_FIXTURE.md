# Rust Core v3.3 Authenticated Read Fixture Pipeline

LQoSync `2.103.0-rc1` / `lqosync-core 3.3.0` adds `run-routeros-authenticated-read-fixture`.

This phase composes the redacted RouterOS auth-session contract with the offline RouterOS session pipeline and the read-result trust contract. It proves the future authenticated-read state machine without opening sockets, sending credentials, or replacing Python collectors.

## Operation

```text
run-routeros-authenticated-read-fixture
```

## Safety status

Still not a full Rust backend:

- No live RouterOS sockets are opened.
- No RouterOS login sentence is sent.
- No username, password, token, or session secret is emitted.
- Python collectors remain authoritative.
- The operation is fixture-only and returns `full_rust_backend=false`.

## Example

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-authenticated-read-fixture \
  -H 'Content-Type: application/json' \
  -d '{
    "router": {"name":"R1","address":"10.0.0.1","username":"admin","password":"secret"},
    "adapter":"fixture",
    "execute":true,
    "fixture_reply_words":["!done"],
    "path":"/ppp/active",
    "fields":["name","address"],
    "fixture_rows":[{"name":"client1","address":"10.0.0.2"}]
  }'
```

Expected fixture status:

```text
authenticated_read_fixture_complete
```

Live adapter requests remain blocked with `routeros_authenticated_read_live_adapter_not_implemented`.

## Why this matters

This is the final offline bridge before a live read-only Rust RouterOS adapter can be introduced. The next stage should be a tightly gated, one-router/one-command live read pilot, with Python collectors still available as fallback.
