# Rust Core v2.2 RouterOS Transport Session Rehearsal

This release adds `build-routeros-transport-session`, a non-network rehearsal layer between the RouterOS read plan and a future live Rust RouterOS API client.

## Status

This is still **not** a full Rust backend.

Python still performs live RouterOS API reads. Rust only builds a redacted transport session plan and confirms that no live network connection or credential use happens in this release.

## Operation

```text
build-routeros-transport-session
```

The operation returns:

- planned routers
- redacted address/credential presence
- command counts per router
- enabled source map
- `connection_attempt_count = 0`
- `live_transport_supported = false`
- `full_rust_backend = false`

## Safety defaults

```json
"rust_core": {
  "routeros_transport_authority": "plan_only",
  "allow_rust_routeros_live_reads": false,
  "allow_rust_routeros_credentials": false
}
```

Any attempt to request `mode=live`, `execute=true`, or `routeros_transport_authority=live_read_pilot` is blocked because live Rust RouterOS transport is not implemented yet.

## API

```text
GET  /api/rust-core/routeros-transport-session
POST /api/rust-core/routeros-transport-session
```

Examples:

```bash
curl "http://YOUR-LQOSYNC/api/rust-core/routeros-transport-session"
curl "http://YOUR-LQOSYNC/api/rust-core/routeros-transport-session?router=RB5k9-Distro&source=pppoe"
```

## Why this phase exists

Before Rust can become responsible for MikroTik reads, it must have a stable transport contract that redacts credentials, blocks accidental live execution, and proves exactly what it would connect to later.
