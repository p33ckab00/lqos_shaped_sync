# Rust Core v2.3 RouterOS Live Read Pilot Gate

This release adds the `build-routeros-live-read-pilot` operation. It is a gated contract for a future read-only Rust RouterOS transport adapter.

## Safety status

This is **not** full Rust backend yet. Rust still does not open RouterOS sockets, consume credentials, or replace Python collectors.

The operation selects one planned RouterOS read command, redacts credential material, checks live-read authority flags, and returns a pilot contract. Even when all authority flags are enabled, v2.3 blocks execution with `routeros_live_transport_adapter_not_implemented`.

## Default config

```json
{
  "rust_core": {
    "routeros_transport_authority": "plan_only",
    "allow_rust_routeros_live_reads": false,
    "allow_rust_routeros_credentials": false,
    "routeros_live_read_pilot": false,
    "routeros_live_read_timeout_seconds": 5
  }
}
```

## Operation

```json
{
  "version": "1",
  "op": "build-routeros-live-read-pilot",
  "payload": {
    "router": "RB5k9-Distro",
    "source": "pppoe",
    "path": "/ppp/active",
    "mode": "rehearsal",
    "execute": false
  }
}
```

## API

```text
GET  /api/rust-core/routeros-live-read-pilot
POST /api/rust-core/routeros-live-read-pilot
```

Examples:

```bash
curl "http://YOUR-LQOSYNC/api/rust-core/routeros-live-read-pilot?router=RB5k9-Distro&source=pppoe"
```

## Why this phase exists

Before adding a real Rust RouterOS client, LQoSync must prove that the live-read pilot gate can:

- select exactly one planned read command,
- avoid exposing passwords,
- reject accidental live execution,
- require all authority flags,
- keep connection attempts at zero until the transport adapter exists.
