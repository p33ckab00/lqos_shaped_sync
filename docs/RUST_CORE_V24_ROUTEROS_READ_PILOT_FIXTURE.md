# Rust Core v2.4 RouterOS Read Pilot Fixture Adapter

LQoSync v2.94.0-rc1 / lqosync-core v2.4.0 adds `run-routeros-read-pilot`.

This operation is the first executable RouterOS read-pilot harness, but it is intentionally offline. It executes only a `fixture` adapter supplied in the request, then validates the resulting rows with the RouterOS read-result contract.

## What it does

- Selects a command using the existing `build-routeros-live-read-pilot` contract.
- Accepts `fixture_rows` for that selected command.
- Builds a RouterOS read-result envelope.
- Validates the result through `validate-routeros-read-results`.
- Reports `safe_for_cleanup`, row count, selected command, and validation status.

## What it does not do

- It does not open RouterOS sockets.
- It does not consume MikroTik credentials.
- It does not replace Python collectors.
- It does not write LibreQoS files.

## API

```text
GET  /api/rust-core/routeros-read-pilot
POST /api/rust-core/routeros-read-pilot
```

Example POST:

```json
{
  "router": "RB5k9-Distro",
  "source": "pppoe",
  "path": "/ppp/active",
  "adapter": "fixture",
  "execute": true,
  "fixture_rows": [
    {"name": "testuser", "address": "10.0.0.2"}
  ]
}
```

Expected status:

```text
fixture_executed
```

## Full Rust backend status

This is still not a full Rust backend. It is an offline adapter harness that lets the Rust core validate the read-pilot execution shape before a future live RouterOS socket transport is introduced.
