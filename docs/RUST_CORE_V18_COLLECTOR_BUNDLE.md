# Rust Core v1.8 Collector Bundle Shadow Builder

Rust Core v1.8 adds a non-authoritative collector-bundle builder. It accepts raw collector snapshots from Python and returns ShapedDevices-compatible rows in shadow mode.

## Operation

```text
build-collector-circuit-bundle
```

## Purpose

This bridges the project from a Rust safety core toward a future Rust backend without replacing Python RouterOS collection yet. Python remains authoritative. Rust receives already-collected rows and proves it can normalize PPPoE, DHCP, and Hotspot data into LibreQoS circuit rows.

## Payload shape

```json
{
  "router": {"name": "RB5009", "pppoe": {"per_plan_node": true}},
  "defaults": {"default_pppoe_rate": "10M/10M", "min_rate_percentage": 0.5},
  "pppoe": {"active": [], "secrets": [], "profiles": []},
  "dhcp": {"leases": [], "servers": []},
  "hotspot": {"active": []}
}
```

## Safety

- Mode is always `shadow`.
- Rust does not connect to RouterOS.
- Rust does not write files.
- Rust does not replace Python collectors.
- Output is diagnostic until a later authority phase explicitly promotes it.

## API

```text
POST /api/rust-core/collector-bundle-shadow
```

This endpoint is read-only from the perspective of production files. It returns the Rust response for an operator-provided JSON payload.

## Full Rust backend status

This is **not** a full Rust backend yet. It is the first collector-processing bridge. Full Rust backend still requires a Rust RouterOS client, a Rust authoritative run-cycle, and production parity gates.
