# Rust Core v3.5 Collector Authority Pilot Gate

Version: `lqosync-core 3.5.0` / LQoSync `2.105.0-rc1`

This release adds the next bridge toward a full Rust backend core: a non-mutating collector authority pilot gate.

## New operation

```text
evaluate-rust-collector-authority-pilot
```

The operation evaluates whether a single collector source is eligible for a future Rust collector authority pilot. It composes the existing live-read adapter contract, collector parity status, source allow-list, and authority flags.

## Safety status

This is still not full Rust backend.

```text
Python collectors remain authoritative.
Rust does not perform live RouterOS reads.
Rust does not switch collector authority.
Rust does not write LibreQoS files.
Rust does not apply cleanup authority.
```

Even when every pilot gate is enabled, v3.5 reports eligibility only. It does not promote Rust to source authority.

## Required pilot gates

For a source to be eligible for a future Rust collector authority pilot, all of these must be true:

```json
{
  "rust_core": {
    "allow_rust_collector_authority": true,
    "rust_collector_authority_pilot": true,
    "allow_rust_routeros_live_read_adapter": true,
    "routeros_live_read_adapter_pilot": true,
    "rust_collector_authority_sources": ["pppoe"],
    "collector_authority_mode": "rust_collector_authority_pilot"
  }
}
```

Collector parity must also be proven, normally with `parity_score >= 99.99` or `verdict=parity_pass`.

## Status values

```text
collector_authority_shadow_only
collector_authority_pilot_gate_ready
blocked
```

`blocked` is returned when the caller tries to execute or promote authority. This release only evaluates the gate.

## API endpoint

```text
GET  /api/rust-core/collector-authority-pilot
POST /api/rust-core/collector-authority-pilot
```

Example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/collector-authority-pilot \
  -H 'Content-Type: application/json' \
  -d '{
    "router": {"name":"RB5k9-Distro"},
    "source":"pppoe",
    "path":"/ppp/active",
    "collector_parity":{"parity_score":100.0,"verdict":"parity_pass"}
  }'
```

Expected default result:

```text
collector_authority_shadow_only
collector_authority=python_authoritative
full_rust_backend=false
```

## Next stage

The next major bridge is the Rust collector live-read pilot, where Rust can start executing a narrowly scoped read path under explicit operator gates while Python remains fallback/authority.

## v3.5.1 redaction-test hotfix

`v3.5.1` fixes a false-positive unit test that checked for the broad word `secret` in the collector authority result. Nested auth/session contract metadata can legitimately contain non-secret labels, so the test now checks only the exact password value and raw `password` key. Runtime behavior is unchanged.
