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


## v1.0 Apply Transaction Executor

`execute-apply-transaction` executes the safe file-write part of a previously previewed apply manifest only when explicitly requested with `execute=true` and `allow_file_writes=true`. It does not run `LibreQoS.py`; Python remains authoritative for external apply execution. By default it behaves as a rehearsal and returns the write plan without mutating files.


## v1.1 self-test

```bash
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

The self-test is read-only and verifies advertised operations, parser basics, apply manifest generation, and transaction rehearsal.


## v1.1.1 build/install hotfix

- Fixes the `self-test` no-change manifest check.
- Prevents stale release binaries from surviving a failed `scripts/build-rust-core.sh`.
- Restarts an active `lqosync-core.service` when installing daemon updates.


## v1.2.0 transaction journal and rollback preview

Adds `build-transaction-journal` and `build-rollback-manifest`. Both operations are non-mutating and intended to make future Rust apply authority auditable and rollback-aware.

## v1.3 transaction journal persistence

New operation: `append-transaction-journal`. It appends the Rust transaction journal event to JSONL only when explicitly requested and allowed. Defaults are rehearsal-only.


## v1.4 transaction history operations

```text
read-transaction-journal
build-rollback-from-journal
```

These operations are read-only and are intended for Operations Center visibility and rollback plan preview.
