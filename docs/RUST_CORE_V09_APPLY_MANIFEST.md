# Rust Core v0.9 Apply Manifest / Transaction Preview

Rust Core v0.9 adds a non-destructive transaction manifest step before Python writes generated files or triggers LibreQoS apply.

## Operation

```text
build-apply-manifest
```

The operation receives current/proposed `ShapedDevices.csv`, current/proposed `network.json`, path settings, Python policy verdict, Rust sync-plan result, and the Rust authority gate result.

It returns a stable manifest:

```json
{
  "manifest_id": "apply-...",
  "status": "ready",
  "write_allowed": true,
  "apply_required": true,
  "backup_required": false,
  "operations": []
}
```

## Why this matters

Before v0.9, the dashboard could show diff and policy diagnostics, but there was no single transaction-style preview describing exactly what would happen next.

v0.9 makes the intended transaction explicit:

1. backup live LibreQoS files if configured;
2. write `ShapedDevices.csv` if changed;
3. write `network.json` if changed;
4. mark pending LibreQoS apply in runtime state;
5. run `LibreQoS.py --updateonly` if policy/config allows.

## Authority model

Python remains authoritative in v0.9. The manifest is diagnostic by default.

The manifest respects the v0.8 Rust authority gate. If the gate would block, the manifest status becomes:

```text
blocked_by_authority_gate
```

but the actual write/apply behavior remains controlled by Python and the existing v0.8 gate logic.

## Dry Run visibility

Dry Run now shows **Rust Apply Manifest Preview** with:

- manifest ID;
- transaction status;
- operation count;
- backup requirement;
- apply requirement;
- full JSON manifest details.

## Next step

A future v1.0 can make this manifest the shared contract between Python and Rust before moving more of the run-cycle transaction into Rust.
