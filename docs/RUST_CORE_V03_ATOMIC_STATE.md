# Rust Core v0.3 Atomic State and File Engine

This package advances the `lqosync-in-rust` branch to the v0.3 safety milestone.

## Goal

Rust now defines protocol operations for atomic state/file writes while Python keeps a safe fallback path. The important change is that runtime state, policy state, collector cache, generated LibreQoS files, and audit JSONL are treated as safety-critical files, not casual writes.

## State files covered

```text
/opt/lqosync/state/runtime_state.json
/opt/lqosync/state/policy_state.json
/opt/lqosync/state/collector_cache.json
/opt/lqosync/logs/audit.jsonl
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/libreqos/src/config.json
```

`collector_cache.json` is included because it can affect source continuity and speed/source metadata across cycles. A corrupt or partial cache write must not silently poison the next run.

## Rust protocol operations

```text
validate-json-state
write-json-state
write-text-file
append-audit-jsonl
```

All use the same transport-neutral protocol envelope documented in `docs/RUST_CORE_PROTOCOL.md`.

## Python fallback

Python remains safe when the Rust binary is unavailable. The fallback now uses:

```text
write temp file
fsync temp file
os.replace
fsync parent directory where supported
```

Audit JSONL appends now flush and fsync the file before returning.

## Opt-in Rust write delegation

By default, Python performs the actual writes. To test Rust-backed atomic writes on a lab install:

```bash
export LQOSYNC_RUST_ATOMIC_WRITES=1
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
```

If the Rust binary is unavailable or an operation fails, Python falls back to its hardened atomic writer.

## Safety model

The v0.3 writer is designed around these rules:

1. Validate JSON state shape before writing where possible.
2. Write into the same directory as the target file.
3. Flush and fsync the temporary file.
4. Rename atomically over the target.
5. Fsync the parent directory where the platform permits it.
6. Return checksums and byte counts from Rust operations.
7. Keep Python fallback behavior available for production stability.

## Not included yet

The policy decision engine itself is still Python. v0.3 hardens state and file persistence only.
## v2.73.1-rc1 build hotfix

The initial v0.3 package used `csv::Terminator::LF`, but the current Rust `csv` crate exposes newline control through `csv::Terminator::Any(b'\n')`. The hotfix updates `rust/lqosync-core/src/shaped_devices.rs` so the Rust core builds cleanly while preserving LF-only `ShapedDevices.csv` rendering.

