# Rust Core v0.6 Circuit Shadow Normalizer

Rust Core v0.6 adds a non-authoritative `normalize-circuits` protocol operation. This is the first circuit-builder migration step. Python collectors and Python builders remain authoritative; Rust now receives normalized circuit records and independently builds a typed ShapedDevices-compatible row view for diagnostics.

## Why this exists

The eventual goal is to move deterministic circuit construction into Rust while keeping RouterOS collection safe and incremental. The v0.6 step does not replace PPPoE, DHCP, or Hotspot collectors. Instead, it verifies the rows Python already produced and reports whether Rust can normalize the same circuit model safely.

## Operation

```json
{
  "version": "1",
  "op": "normalize-circuits",
  "payload": {
    "source": "mixed",
    "router": "mixed",
    "min_rate_percentage": 0.5,
    "records": []
  }
}
```

The result includes:

```text
input_count
normalized_count
invalid_count
warning_count
source_counts
normalized_rows
```

The operation can detect:

```text
missing circuit name/code
missing parent node
invalid or missing speed
duplicate IPv4
unusual min/max ratios
```

## Safety

This is shadow-only. Python remains authoritative for live row generation. Rust diagnostics are shown in Dry Run as `rust_circuit_shadow` and are not allowed to change write/apply decisions in this release.

## Relationship to future work

This prepares the path for a future migration where:

```text
Python RouterOS API reads raw rows
↓
Rust normalizes PPP/DHCP/Hotspot records
↓
Rust builds ShapedDevices rows
↓
Python displays and orchestrates
```

A later release can make this authoritative only after parity is proven across production dry-runs.
