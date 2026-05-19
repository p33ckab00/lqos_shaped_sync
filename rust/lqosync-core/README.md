# lqosync-core

`lqosync-core` is the optional Rust safety sidecar for LQoSync.

Current scope:

- stable JSON protocol envelope
- bandwidth parser
- ShapedDevices.csv parser/render validator
- network.json parser/tree validator
- config/policy action validator
- collector output trust validator

Python remains the WebUI and orchestrator. If this binary is missing, Python uses
the existing validation path and records a fallback status.

## Build

```bash
scripts/build-rust-core.sh
```

## Install optional binary

```bash
sudo scripts/install-rust-core.sh
```

## Example request

```bash
printf '%s' '{"version":"1","op":"parse-bandwidth","payload":{"parser":"rate_limit","value":"10M/5M"}}' \
  | rust/lqosync-core/target/release/lqosync-core
```
## v0.2 operations

The v0.2 core adds trust/diff operations:

```text
validate-collector-output
diff-shaped-devices
diff-network
diff-files
```

`validate-collector-output` protects cleanup eligibility from silent partial or suspicious zero collector results. `diff-files` compares current/proposed ShapedDevices and network JSON text and returns added/removed/updated summaries.



## v0.3 atomic state operations

```text
validate-json-state
write-json-state
write-text-file
append-audit-jsonl
```

These operations use the stable protocol envelope and are intended for both the current CLI and future Unix socket daemon.


## v0.4 daemon mode

The Rust core can run as a long-lived Unix socket daemon using the same JSON protocol as the CLI:

```bash
lqosync-core --daemon --socket /run/lqosync-core.sock
```

Install as a systemd service after building/installing the binary:

```bash
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
sudo scripts/install-rust-core-daemon.sh
```

Python uses the daemon only when `rust_core.prefer_daemon=true` and the socket exists. If the daemon is unavailable, the wrapper falls back to subprocess or Python fallback.


## v0.5 Policy Shadow

`evaluate-policy` computes a non-authoritative policy verdict, risk score, write/apply hints, and parity against Python policy decisions.


## v0.6 Circuit Shadow

`normalize-circuits` builds a typed ShapedDevices-compatible row view from normalized circuit records. It is diagnostic/shadow-only and prepares for a future Rust circuit builder while Python remains authoritative.

## v0.7.0 Operation

`evaluate-sync-plan` composes collector trust, diff, validation, policy shadow, circuit shadow, preflight, and cleanup stats into one non-authoritative sync plan.


## v0.8 authority gates

The Rust core can now annotate sync plans with authority metadata. Python enforces the gate only when `rust_core.enforce_sync_plan=true` or `authority_mode=enforce_blockers`.


## v0.9 Apply Manifest

Adds `build-apply-manifest`, a non-destructive transaction preview that lists backup, file-write, pending-apply, and LibreQoS apply operations before Python performs them. It is diagnostic by default and designed for future controlled Rust transaction authority.
