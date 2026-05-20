## v3.3 Authenticated Read Fixture Pipeline

Adds `run-routeros-authenticated-read-fixture`, composing auth session, offline session, and read-result validation without network access.

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


## v1.5 rollback executor

Adds `execute-rollback`, default rehearsal-only, with explicit `CONFIRM_ROLLBACK` and file-write gates required for real restore operations.


## v1.6 Authority Readiness

Adds `evaluate-authority-readiness`, a read-only operation for checking Rust authority readiness before enabling enforcement, file writes, journal persistence, or rollback restores.


## v1.7 Full Backend Readiness

New operations: `evaluate-full-rust-readiness` and `build-authority-pilot-plan`. These are read-only helpers for distinguishing hybrid authority-pilot status from a future full Rust backend.


## v1.8.0

Adds `build-collector-circuit-bundle`, a shadow operation that normalizes raw PPPoE/DHCP/Hotspot collector snapshots into ShapedDevices-compatible rows.


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.


## v2.0 RouterOS Collector Plan

`build-routeros-collector-plan` produces a deterministic RouterOS read plan from LQoSync config.

It is a plan-only operation:
- no RouterOS socket is opened;
- no credentials are used;
- no files are written;
- Python collectors remain authoritative.

The operation is a bridge toward a future Rust RouterOS transport by freezing the expected RouterOS resources, selected fields, and source trust roles before live collection is migrated.


## v2.0.1 script permission hotfix

If scripts are not executable after extracting a package:

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
```

The v2.0+ self-test should advertise `build-routeros-collector-plan`.


## Rust Core v2.1 RouterOS Read Result Contract

This package adds `validate-routeros-read-results`, a Rust trust contract that validates Python-executed RouterOS read results against the deterministic collector plan. It is diagnostic by default and does not replace Python live RouterOS collectors.


## Rust Core v2.2 RouterOS Transport Session Rehearsal

Adds `build-routeros-transport-session`, a non-network RouterOS transport rehearsal that redacts credentials, reports planned sessions, blocks live Rust RouterOS transport attempts, and keeps Python live collectors authoritative.


## v2.3 RouterOS Live Read Pilot Gate

Adds `build-routeros-live-read-pilot` as a non-network, credential-redacted pilot contract before implementing a real RouterOS read-only transport adapter.


## Rust Core v2.4 RouterOS Read Pilot Fixture Adapter

Adds `run-routeros-read-pilot`, an offline fixture adapter that exercises the RouterOS read-pilot execution contract without opening MikroTik sockets or replacing Python collectors.

## v2.5.0

Adds `build-routeros-api-sentence`, an offline RouterOS API sentence/proplist codec.


## Rust Core v2.6 RouterOS API Reply Codec

Adds `decode-routeros-api-reply`, an offline RouterOS API reply parser that decodes already-captured `!re`/`!trap`/`!done` words into sanitized rows/traps while keeping Rust RouterOS live transport disabled by default.

## v2.7 RouterOS API Frame Codec

Adds `codec-routeros-api-frame` for offline RouterOS API binary frame encode/decode with no socket access.


## Rust Core v2.8 RouterOS Offline Session Pipeline

Adds `run-routeros-offline-session`, an end-to-end offline RouterOS API session rehearsal. It composes sentence encoding, frame encoding/decoding, and reply decoding using fixtures only. It performs zero live connections, consumes no MikroTik credentials, and keeps Python collectors authoritative.


## v2.9 RouterOS TCP Connectivity Pilot

Adds `run-routeros-tcp-connectivity-pilot`, a gated TCP reachability pilot. Rehearsal mode performs no network connection. Explicit execution never authenticates or sends RouterOS API words.


## v3.0 RouterOS Authentication Plan

Adds `build-routeros-auth-plan` for redacted auth planning. This does not authenticate or expose credential material; it prepares the future live read-only RouterOS adapter.


## v3.1 Auth Handshake Fixture

Adds `run-routeros-auth-handshake`, an offline RouterOS auth handshake fixture. It redacts credentials, decodes fixture login replies, and performs zero live connection/auth attempts.


## Rust Core v3.2 RouterOS Auth Session Contract

Adds `build-routeros-auth-session-contract`, a redacted authenticated-session contract built from fixture auth replies. It performs zero socket/auth attempts, emits no credentials or tokens, and keeps Python collectors authoritative.


## v3.4 Live Read Adapter Contract

This package adds Rust Core `v3.4.0` / LQoSync `2.104.0-rc1` with `run-routeros-live-read-adapter-pilot`. It is still not a full Rust backend: the operation builds a guarded live-read adapter contract only and does not open RouterOS sockets, authenticate, send API words, read replies, or replace Python collectors.

## v3.5 Collector Authority Pilot Gate

New operation: `evaluate-rust-collector-authority-pilot`.

This operation evaluates whether a collector source is eligible for a future Rust collector authority pilot. It does not perform live reads, does not switch authority, and keeps Python collectors authoritative.

## v3.6

Adds `build-collector-authority-manifest` for non-mutating collector authority decision manifests.

## v3.7 Collector authority dry-run selection

Adds `build-collector-authority-selection`, which is dry-run only and keeps Python collectors authoritative.


## Rust Core v3.8 Collector Authority Dry-Run Bundle

Adds `build-collector-authority-dry-run-bundle`, a non-mutating Rust-shadow bundle that combines collector authority selection, normalized Rust rows, and parity reporting. Python remains production-authoritative; Rust rows cannot drive cleanup or apply.


## v3.9 run_cycle Rust-Shadow Report

Adds `build-run-cycle-rust-shadow-report`, a non-mutating operation for Python run_cycle diagnostic integration.


## Rust Core v4.0 Collector Authority Activation Plan

Adds `build-collector-authority-activation-plan`, a non-mutating activation readiness plan for the future Rust collector authority pilot. It requires a clean run_cycle Rust-shadow report, successful shadow-cycle history, explicit activation gates, and Python fallback. Python collectors remain authoritative; Rust cannot drive cleanup, writes, or apply in this release.


## Rust Core v4.1 Collector Authority Runtime Contract

Adds `build-collector-authority-runtime-contract`, a non-mutating runtime contract after the collector authority activation plan. Python collectors remain authoritative; Rust cannot drive cleanup, apply, or generated-file writes from this contract. See `docs/RUST_CORE_V41_COLLECTOR_AUTHORITY_RUNTIME.md`.


## Rust Core v4.2 Collector Authority Switch Rehearsal

Adds `build-collector-authority-switch-rehearsal`, a non-mutating rehearsal layer after the collector authority runtime contract. It never switches production authority and keeps Python fallback mandatory.


## Rust Core v4.3 Collector Authority Pilot Execution Contract

Adds `build-collector-authority-pilot-execution-contract`, a non-mutating contract after the collector authority switch rehearsal. It requires explicit gates, the `CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION` token, fresh Rust-shadow data, and Python fallback. It does not switch production collector authority, drive cleanup, write generated files, or apply LibreQoS. See `docs/RUST_CORE_V43_COLLECTOR_AUTHORITY_PILOT_EXECUTION.md`.


### v4.3.1

Fixes a compile-time recursion limit issue in the collector authority pilot execution contract response construction.

### v4.3.2

Fixes collector authority pilot execution readiness by separating switch-rehearsal confirmation from pilot-execution confirmation. This remains a non-mutating contract-only bridge.


## v4.4 operation

`evaluate-collector-authority-pilot-result` evaluates a future collector authority pilot result without allowing Rust to drive cleanup, writes, apply, or production collector authority.

## v4.5 Collector Authority Promotion Readiness

Adds `build-collector-authority-promotion-readiness`, a non-mutating readiness report after `evaluate-collector-authority-pilot-result`. It requires explicit gates and `CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS` before reporting ready, but it does not promote Rust collectors or transfer cleanup/apply/write authority.
