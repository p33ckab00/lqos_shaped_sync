# Rust Core v0.2 Trust and Diff Update

This document describes the second major Rust-core integration step in the `lqosync-in-rust` branch.

## Purpose

v0.1 added the optional Rust safety core scaffold. v0.2 makes the safety boundary more useful during real sync cycles by adding two protections:

1. **Collector output trust guard** before cleanup eligibility.
2. **Rust diff operations** for ShapedDevices and network impact summaries.

The Python WebUI and scheduler remain the primary runtime. Rust remains optional and fallback-safe.

## Collector trust guard

Before v0.2, a collector processor could return an empty list without throwing an exception. The old success path could still mark a source as scanned successfully. If previous rows existed, cleanup policy could then classify those rows as inactive and remove them.

v0.2 adds an explicit trust envelope for each router/source processor result:

```json
{
  "router": "RB5009-Core",
  "source": "PPP",
  "status": "ok",
  "rows": ["client-a", "client-b"],
  "previous_success_count": 20,
  "failed_reads": [],
  "read_counts": {},
  "metrics": {}
}
```

The trust validator returns:

```json
{
  "safe_for_cleanup": true,
  "row_count": 2,
  "write_allowed": true,
  "apply_allowed": true
}
```

If a source returns zero rows after a previous successful non-zero run, the result becomes suspicious:

```json
{
  "safe_for_cleanup": false,
  "row_count": 0
}
```

In that case, LQoSync does **not** add the source to `cleanup_sources`. Existing rows for that source are preserved until a trusted scan or explicit policy handling is available.

## Python fallback still enforces the contract

The wrapper in `engine/rust_core.py` includes a local Python implementation of the collector trust contract. This means the silent-empty-list protection works even before the Rust binary is built.

When the Rust binary is available, Python calls:

```text
validate-collector-output
```

When the Rust binary is unavailable, Python uses:

```text
python_contract_fallback
```

Both modes use the same response shape.

## Rust diff operations

v0.2 adds these Rust operations:

```text
diff-shaped-devices
diff-network
diff-files
```

`diff-files` accepts:

```json
{
  "current_csv_text": "...",
  "proposed_csv_text": "...",
  "current_network_text": "...",
  "proposed_network_text": "..."
}
```

It returns:

```json
{
  "csv": {
    "current_count": 10,
    "proposed_count": 12,
    "added_count": 2,
    "removed_count": 0,
    "updated_count": 1,
    "changed": true
  },
  "network": {
    "current_node_count": 4,
    "proposed_node_count": 5,
    "added_node_count": 1,
    "removed_node_count": 0,
    "changed": true
  },
  "changed": true
}
```

The existing Python diff remains the UI-compatible primary diff. The Rust diff is stored under:

```text
result.diff.rust_core_diff
```

## Dry Run visibility

Dry Run now shows a Rust Diff and Collector Trust panel. It exposes:

- Rust diff availability and result.
- CSV change count from the Rust diff.
- Network changed status from the Rust diff.
- Number of collector trust checks performed.
- Full JSON diagnostics for troubleshooting.

## Cleanup safety behavior

The key safety rule is:

```text
A source is only eligible for cleanup if the collector trust result says safe_for_cleanup=true.
```

This protects against:

- RouterOS API returning an empty list without exception.
- Partial resource reads.
- Suspicious zero-result after previous successful data.
- Future typed collector failures.

## What v0.2 does not change

v0.2 does not replace the Python collectors, policy engine, file writer, or WebUI.

It does not enable Rust enforcement by default.

It does not run LibreQoS differently.

## Next milestone

The next milestone should be v0.3: Rust atomic state/file engine for:

```text
config.json
runtime_state.json
policy_state.json
collector_cache.json
ShapedDevices.csv
network.json
audit.jsonl append
backup manifest
```
