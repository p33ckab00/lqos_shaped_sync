## v3.3 commit suggestion

```bash
git add .
git commit -m "rust(core): add authenticated RouterOS read fixture" \
  -m "Add run-routeros-authenticated-read-fixture, a fixture-only authenticated read pipeline that composes auth-session contract, offline RouterOS session, and read-result trust before live Rust RouterOS reads."
git push -u origin lqosync-in-rust
```

# Commit and Push Guide for `lqosync-in-rust`

> **Canonical path:** LQoSync installs and runs from `/opt/lqosync`. LibreQoS remains under `/opt/libreqos`. Do not use a user-home directory as the documented install base.


Use this guide whenever a new ZIP package or local project folder is prepared for the Rust migration branch.

Target branch:

```text
lqosync-in-rust
```

## Recommended branch model

Use `main` for the stable Python/Flask LQoSync line. Use `lqosync-in-rust` for the hybrid Rust-core migration.

```text
main
  └─ lqosync-in-rust
       ├─ protocol scaffold
       ├─ Rust validator core
       ├─ collector contract
       ├─ atomic state engine
       └─ future daemon/policy/circuit work
```

## If starting from a fork

```bash
# Clone your fork
cd /opt
git clone https://github.com/YOUR_GITHUB_USERNAME/LQoSync.git LQoSync-rust
cd LQoSync-rust

# Add upstream original, if needed
git remote add upstream https://github.com/p33ckab00/LQoSync.git

git fetch origin
git fetch upstream

# Start from latest main
git checkout main
git pull origin main

# Create the Rust migration branch
git checkout -b lqosync-in-rust
```

## If starting from the provided ZIP package

```bash
# Example location only
cd /opt
unzip /path/to/LQoSync_runtime_canonical_FULL_rust_core_scaffold.zip -d LQoSync-rust
cd LQoSync-rust

# If this folder is not yet a Git repo
git init
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/LQoSync.git

# Create migration branch
git checkout -b lqosync-in-rust
```

If the repo already exists:

```bash
cd /opt/LQoSync
git fetch origin
git checkout main
git pull origin main
git checkout -b lqosync-in-rust
```

If the branch already exists:

```bash
git fetch origin
git checkout lqosync-in-rust
git pull origin lqosync-in-rust
```

## Apply files from a new ZIP into an existing branch

```bash
# From existing repo branch
cd /opt/LQoSync
git checkout lqosync-in-rust

# Optional: backup current working tree outside git
mkdir -p /opt/lqosync-branch-backups
rsync -a --delete ./ /opt/lqosync-branch-backups/LQoSync-before-$(date +%Y%m%d-%H%M%S)/

# Extract new ZIP into a temporary directory
rm -rf /tmp/lqosync-new
mkdir -p /tmp/lqosync-new
unzip /path/to/LQoSync_runtime_canonical_FULL_rust_core_scaffold.zip -d /tmp/lqosync-new

# Copy new files into repo, preserving .git
rsync -a --delete --exclude '.git' /tmp/lqosync-new/ ./
```

## Review before commit

Always inspect changes before committing:

```bash
git status
git diff --stat
git diff -- README.md docs/DOCUMENTATION_INDEX.md docs/RUST_CORE_MIGRATION.md docs/RUST_CORE_PROTOCOL.md docs/COLLECTOR_OUTPUT_CONTRACT.md docs/AUTOSAVE_AND_ATOMIC_STATE.md docs/COMMIT_AND_PUSH_GUIDE.md
```

Optional documentation syntax checks:

```bash
python3 -m json.tool docs/docs_manifest.json >/dev/null
python3 - <<'PY'
from pathlib import Path
required = [
    'docs/RUST_CORE_MIGRATION.md',
    'docs/RUST_CORE_PROTOCOL.md',
    'docs/COLLECTOR_OUTPUT_CONTRACT.md',
    'docs/AUTOSAVE_AND_ATOMIC_STATE.md',
    'docs/COMMIT_AND_PUSH_GUIDE.md',
]
for item in required:
    assert Path(item).exists(), item
print('documentation files present')
PY
```

If Python dependencies are installed, run lightweight self-checks:

```bash
python3 scripts/validate_config_example.py || true
python3 scripts/release_check.py || true
python3 scripts/stable_release_check.py || true
```

Use `|| true` only when running checks on a development machine that may not have the full LibreQoS environment.

## Commit command for this documentation package

Recommended commit subject:

```text
docs(rust): document LQoSync-in-Rust migration plan
```

Recommended commit body:

```text
Document the lqosync-in-rust branch strategy, Rust core protocol, collector output safety contract, autosave/atomic state model, and commit/push workflow.

Key points:
- keep Python Flask WebUI as operator interface
- add Rust core as deterministic safety boundary
- preserve pure JSON/file state model with no database
- include collector_cache.json in atomic state engine scope
- define transport-neutral JSON protocol for CLI and future Unix socket daemon
- document branch, review, commit, and push workflow
```

Copy-paste command:

```bash
git add   README.md   FULL_DOCUMENTATION.md   RELEASE_NOTES.md   PACKAGE_NOTES.md   docs/DOCUMENTATION_INDEX.md   docs/docs_manifest.json   docs/RUST_CORE_MIGRATION.md   docs/RUST_CORE_PROTOCOL.md   docs/COLLECTOR_OUTPUT_CONTRACT.md   docs/AUTOSAVE_AND_ATOMIC_STATE.md   docs/COMMIT_AND_PUSH_GUIDE.md   docs/assets/lqosync_rust_migration_plan.svg   engine/docs_search.py

git commit -m "docs(rust): document LQoSync-in-Rust migration plan"   -m "Document the lqosync-in-rust branch strategy, Rust core protocol, collector output safety contract, autosave/atomic state model, and commit/push workflow."   -m "Key points: keep Python Flask WebUI as the operator interface, add Rust core as deterministic safety boundary, preserve the pure JSON/file model, include collector_cache.json in atomic state scope, and define a transport-neutral protocol for CLI and future Unix socket daemon."
```

## Push command

First push of the branch:

```bash
git push -u origin lqosync-in-rust
```

Later pushes:

```bash
git push
```

## Pull request description template

```markdown
## Summary

This PR documents the planned `lqosync-in-rust` branch.

## Added

- Rust core migration roadmap
- Python ↔ Rust protocol envelope
- Collector output safety contract
- Autosave and atomic state model
- Commit/push workflow guide

## Safety notes

- No runtime behavior change in this documentation package.
- Python Flask WebUI remains the operator interface.
- Rust is planned as a sidecar/core safety boundary first.
- No database is introduced.
- `collector_cache.json` is included in the future atomic state engine scope.

## Test / review

- [ ] `python3 -m json.tool docs/docs_manifest.json`
- [ ] Documentation links reviewed
- [ ] Git diff reviewed before merge
```

## Commit rhythm for future Rust phases

Use small, reviewable commits:

```text
docs(rust): document protocol envelope
rust(core): scaffold lqosync-core crate
rust(core): add bandwidth parser tests
rust(core): add shaped devices parser
python(core): add rust_core wrapper
rust(core): add collector output contract validation
rust(core): add atomic state writer
```

Avoid one huge commit that mixes docs, Rust code, Python wrapper changes, and UI changes.

## Safety rule before every push

Before pushing, answer these questions:

```text
1. Did this change modify production write/apply behavior?
2. Did this change touch config.json defaults?
3. Did this change touch ShapedDevices.csv/network.json generation?
4. Did this change touch cleanup policy or source trust?
5. Did this change preserve Python fallback?
6. Did this change update docs when behavior changed?
```

If the answer to 1–4 is yes, include a detailed commit body and run dry-run tests before production use.

## Commit command for the Rust scaffold package

Use this when committing the first actual Rust-core scaffold package.

```bash
git add \
  VERSION \
  README.md \
  FULL_DOCUMENTATION.md \
  RELEASE_NOTES.md \
  PACKAGE_NOTES.md \
  config.json.example \
  app.py \
  engine/config_loader.py \
  engine/run_cycle.py \
  engine/rust_core.py \
  templates/dry_run.html \
  scripts/build-rust-core.sh \
  scripts/install-rust-core.sh \
  rust/lqosync-core/Cargo.toml \
  rust/lqosync-core/README.md \
  rust/lqosync-core/src/lib.rs \
  rust/lqosync-core/src/main.rs \
  rust/lqosync-core/src/protocol.rs \
  rust/lqosync-core/src/bandwidth.rs \
  rust/lqosync-core/src/shaped_devices.rs \
  rust/lqosync-core/src/network.rs \
  rust/lqosync-core/src/validators.rs \
  docs/RUST_CORE_MIGRATION.md \
  docs/RUST_CORE_PROTOCOL.md \
  docs/COLLECTOR_OUTPUT_CONTRACT.md \
  docs/AUTOSAVE_AND_ATOMIC_STATE.md \
  docs/COMMIT_AND_PUSH_GUIDE.md

git commit -m "rust(core): scaffold optional LQoSync safety core" \
  -m "Add the first lqosync-core Rust crate with the stable JSON protocol envelope, bandwidth parser, ShapedDevices/network validators, collector output trust validator, Python subprocess wrapper, Dry Run visibility, and build/install helper scripts." \
  -m "Rust validation is optional and non-blocking by default. Python fallback remains active when the Rust binary is unavailable."
```

Push:

```bash
git push -u origin lqosync-in-rust
```

Additional checks when Rust is installed:

```bash
scripts/build-rust-core.sh
printf '%s' '{"version":"1","op":"parse-bandwidth","payload":{"parser":"rate_limit","value":"10M/5M"}}' \
  | rust/lqosync-core/target/release/lqosync-core
```


## v0.3 Atomic State/File Engine commit

```bash
git add .
git commit -m "rust(core): add atomic state and file engine" \
  -m "Add Rust protocol operations for JSON state validation, atomic JSON/text writes, and audit JSONL appends." \
  -m "Harden Python fallback writes and move runtime_state, policy_state, collector_cache, and audit logs onto shared safe writer helpers."
git push -u origin lqosync-in-rust
```


## v0.4 daemon mode commit

```bash
git add .
git commit -m "rust(core): add optional daemon transport" \
  -m "Add Unix socket daemon mode for lqosync-core, Python wrapper daemon transport, systemd service helpers, and daemon documentation while preserving subprocess and Python fallback behavior."
git push -u origin lqosync-in-rust
```


## v0.5 policy shadow commit

```bash
git add .
git commit -m "rust(core): add policy shadow evaluator" \
  -m "Add non-authoritative Rust evaluate-policy operation, Python wrapper integration, Dry Run policy shadow visibility, and documentation for comparing Rust and Python policy decisions before future enforcement."
git push -u origin lqosync-in-rust
```


## v0.6 circuit shadow commit

```bash
git add .
git commit -m "rust(core): add circuit shadow normalizer" \
  -m "Add non-authoritative Rust normalize-circuits operation, Python wrapper integration, Dry Run circuit shadow visibility, and documentation for the future Rust circuit-builder migration."
git push -u origin lqosync-in-rust
```

## v2.77.0-rc1 Commit

```bash
git add .
git commit -m "rust(core): add sync plan shadow engine" \
  -m "Add evaluate-sync-plan to lqosync-core, Python wrapper integration, Dry Run sync plan visibility, and documentation for end-to-end shadow planning before any Rust authority migration."
git push -u origin lqosync-in-rust
```


## v0.8 commit example

```bash
git add .
git commit -m "rust(core): add opt-in sync plan authority gate" \
  -m "Add rust_core.enforce_sync_plan and authority_mode=enforce_blockers so operators can opt into Rust sync-plan blocker enforcement while keeping Python default behavior unchanged."
git push -u origin lqosync-in-rust
```


## v0.9 Commit Example

```bash
git add .
git commit -m "rust(core): add apply manifest preview" \
  -m "Add build-apply-manifest to lqosync-core, Python wrapper integration, Dry Run transaction preview, and documentation for backup/write/pending-apply/LibreQoS apply intent before future Rust transaction authority."
git push -u origin lqosync-in-rust
```


## v1.0 commit

```bash
git add .
git commit -m "rust(core): add apply transaction executor" \
  -m "Add execute-apply-transaction to lqosync-core with rehearsal-only defaults, opt-in file-write execution, Dry Run visibility, and documentation while keeping Python authoritative."
git push -u origin lqosync-in-rust
```


## v2.81.0-rc1 commit example

```bash
git add .
git commit -m "rust(core): add runtime self-test and capability audit"   -m "Route execute-apply-transaction through the Rust CLI/daemon protocol, add the self-test operation, expose /api/rust-core/self-test, and document capability checks before enabling authority flags."
git push -u origin lqosync-in-rust
```


## v2.81.1-rc1 commit example

```bash
git add .
git commit -m "rust(core): fix self-test and daemon reinstall flow" \
  -m "Fix the Rust self-test no-change manifest check, prevent stale release binaries after failed builds, and restart the Rust core daemon after binary updates."
git push -u origin lqosync-in-rust
```

## v2.82.0-rc1 commit example

```bash
git add .
git commit -m "rust(core): add transaction journal and rollback preview" \
  -m "Add build-transaction-journal and build-rollback-manifest operations, Dry Run visibility, transaction_journal path defaults, and documentation for auditable Rust apply transaction accountability."
git push -u origin lqosync-in-rust
```

## v1.3 transaction journal persistence commit

```bash
git add .
git commit -m "rust(core): add transaction journal persistence" \
  -m "Add append-transaction-journal, opt-in journal write flags, Dry Run journal append visibility, and documentation for auditable Rust apply transaction persistence."
git push -u origin lqosync-in-rust
```


## Suggested commit for v1.4

```bash
git add .
git commit -m "rust(core): add transaction history reader" \
  -m "Add read-transaction-journal and build-rollback-from-journal operations, read-only WebUI APIs, self-test coverage, and documentation for rollback plan inspection without rollback execution."
git push -u origin lqosync-in-rust
```


### v1.5 rollback execution rehearsal

```bash
git add .
git commit -m "rust(core): add rollback execution rehearsal" \
  -m "Add execute-rollback, rollback confirmation gates, Python wrapper/API integration, and documentation for opt-in file restore rollback authority."
git push -u origin lqosync-in-rust
```


## v1.6 Authority Readiness commit

```bash
git add .
git commit -m "rust(core): add authority readiness evaluator" \
  -m "Add evaluate-authority-readiness, read-only WebUI API visibility, self-test coverage, and documentation for piloting Rust authority flags safely."
git push -u origin lqosync-in-rust
```


## Commit for Rust Core v1.7

```bash
git add .
git commit -m "rust(core): add full backend readiness evaluator" \
  -m "Add evaluate-full-rust-readiness and build-authority-pilot-plan operations, read-only WebUI APIs, self-test coverage, and documentation for staged Rust authority migration without claiming full Rust backend status."
git push -u origin lqosync-in-rust
```


## v2.88.0-rc1 commit

```bash
git add .
git commit -m "rust(core): add collector bundle shadow builder" \
  -m "Add build-collector-circuit-bundle, self-test coverage, API wrapper, and documentation for shadow Rust normalization of raw collector snapshots."
git push -u origin lqosync-in-rust
```


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.


## Rust Core v2.0 RouterOS Collector Plan

This package adds `build-routeros-collector-plan`, a read-only Rust operation that derives the RouterOS resource/field plan for enabled PPPoE, DHCP, and Hotspot sources. It does not connect to MikroTik and does not replace Python collectors. It is a bridge toward a future Rust RouterOS transport while keeping Python authoritative by default.

New API:

```text
GET /api/rust-core/routeros-collector-plan
POST /api/rust-core/routeros-collector-plan
```


## Commit example — v2.90.1-rc1

```bash
git add .
git commit -m "packaging(rust): fix script permission deployment issue" \
  -m "Add script permission repair helper, preserve executable bits for Rust build/install helpers, and document bash fallback commands for ZIP/manual installs."
git push -u origin lqosync-in-rust
```


## Rust Core v2.1 RouterOS Read Result Contract

This package adds `validate-routeros-read-results`, a Rust trust contract that validates Python-executed RouterOS read results against the deterministic collector plan. It is diagnostic by default and does not replace Python live RouterOS collectors.


## Rust Core v2.2 RouterOS Transport Session Rehearsal

Adds `build-routeros-transport-session`, a non-network RouterOS transport rehearsal that redacts credentials, reports planned sessions, blocks live Rust RouterOS transport attempts, and keeps Python live collectors authoritative.


## v2.3 commit

```bash
git add .
git commit -m "rust(core): add RouterOS live-read pilot gate" \
  -m "Add build-routeros-live-read-pilot, a gated non-network contract for future read-only Rust RouterOS transport, with API wrapper, self-test coverage, and documentation."
git push -u origin lqosync-in-rust
```


## Rust Core v2.4 RouterOS Read Pilot Fixture Adapter

Adds `run-routeros-read-pilot`, an offline fixture adapter that exercises the RouterOS read-pilot execution contract without opening MikroTik sockets or replacing Python collectors.

## v2.95.0-rc1 commit suggestion

```bash
git add .
git commit -m "rust(core): add RouterOS API sentence codec" \
  -m "Add build-routeros-api-sentence, offline RouterOS API print/proplist encoding, self-test coverage, Python/API wrapper, and documentation before live Rust RouterOS socket transport."
git push -u origin lqosync-in-rust
```


## Rust Core v2.6 RouterOS API Reply Codec

Adds `decode-routeros-api-reply`, an offline RouterOS API reply parser that decodes already-captured `!re`/`!trap`/`!done` words into sanitized rows/traps while keeping Rust RouterOS live transport disabled by default.

## v2.7 commit

```bash
git add .
git commit -m "rust(core): add RouterOS API frame codec" \
  -m "Add codec-routeros-api-frame, offline RouterOS API binary frame encode/decode, API wrapper, self-test coverage, and documentation before live Rust socket transport."
git push -u origin lqosync-in-rust
```


## Rust Core v2.8 RouterOS Offline Session Pipeline

Adds `run-routeros-offline-session`, an end-to-end offline RouterOS API session rehearsal. It composes sentence encoding, frame encoding/decoding, and reply decoding using fixtures only. It performs zero live connections, consumes no MikroTik credentials, and keeps Python collectors authoritative.


## v2.99.0-rc1 commit example

```bash
git add .
git commit -m "rust(core): add RouterOS TCP connectivity pilot" \
  -m "Add run-routeros-tcp-connectivity-pilot, gated TCP reachability checks, Python/API wrapper, self-test coverage, and documentation before RouterOS authentication or live API reads."
git push -u origin lqosync-in-rust
```


### v3.2 commit example

```bash
git add .
git commit -m "rust(core): add RouterOS auth session contract" \
  -m "Add build-routeros-auth-session-contract, a redacted authenticated-session contract built from offline auth fixtures before live Rust authenticated reads."
git push -u origin lqosync-in-rust
```


## v3.4 Live Read Adapter Contract

This package adds Rust Core `v3.4.0` / LQoSync `2.104.0-rc1` with `run-routeros-live-read-adapter-pilot`. It is still not a full Rust backend: the operation builds a guarded live-read adapter contract only and does not open RouterOS sockets, authenticate, send API words, read replies, or replace Python collectors.

## Commit for Rust Core v3.5 Collector Authority Pilot

```bash
git add .
git commit -m "rust(core): add collector authority pilot gate" \
  -m "Add evaluate-rust-collector-authority-pilot, a non-mutating source-level authority eligibility gate that keeps Python collectors authoritative while preparing future Rust collector live-read pilot migration."
git push -u origin lqosync-in-rust
```

## v3.6 Collector authority manifest commit

```bash
git add .
git commit -m "rust(core): add collector authority decision manifest" \
  -m "Add build-collector-authority-manifest, a non-mutating per-source manifest for future Rust collector authority migration while keeping Python collectors authoritative."
git push -u origin lqosync-in-rust
```


## Suggested commit for Rust Core v3.7

```bash
git add .
git commit -m "rust(core): add collector authority dry-run selection" \
  -m "Add build-collector-authority-selection, a non-mutating selector that maps collector authority manifest decisions into dry-run Python/Rust-shadow source choices while keeping production collector authority in Python."
git push -u origin lqosync-in-rust
```


## v3.8 Collector Authority Dry-Run Bundle

```bash
git add .
git commit -m "rust(core): add collector authority dry-run bundle" \
  -m "Add build-collector-authority-dry-run-bundle, a non-mutating Rust-shadow bundle that combines collector authority selection, normalized rows, and parity while keeping Python collectors authoritative."
git push -u origin lqosync-in-rust
```


### v3.9 run_cycle Rust-shadow report

Suggested commit:

```bash
git add .
git commit -m "rust(core): add run_cycle Rust-shadow report" \
  -m "Add build-run-cycle-rust-shadow-report, Python run_cycle diagnostic integration, API wrapper, config defaults, and documentation while keeping Python collector cleanup/apply authority."
git push -u origin lqosync-in-rust
```


## Rust Core v4.0 Collector Authority Activation Plan

Adds `build-collector-authority-activation-plan`, a non-mutating activation readiness plan for the future Rust collector authority pilot. It requires a clean run_cycle Rust-shadow report, successful shadow-cycle history, explicit activation gates, and Python fallback. Python collectors remain authoritative; Rust cannot drive cleanup, writes, or apply in this release.


## Rust Core v4.1 Collector Authority Runtime Contract

Adds `build-collector-authority-runtime-contract`, a non-mutating runtime contract after the collector authority activation plan. Python collectors remain authoritative; Rust cannot drive cleanup, apply, or generated-file writes from this contract. See `docs/RUST_CORE_V41_COLLECTOR_AUTHORITY_RUNTIME.md`.


## v4.2 commit example

```bash
git add .
git commit -m "rust(core): add collector authority switch rehearsal" \
  -m "Add build-collector-authority-switch-rehearsal, a non-mutating switch rehearsal after the runtime contract that requires explicit gates, manual confirmation, and Python fallback while keeping production collector authority in Python."
git push -u origin lqosync-in-rust
```


## Suggested commit for Rust Core v4.3

```bash
git add .
git commit -m "rust(core): add collector authority pilot execution contract" \
  -m "Add build-collector-authority-pilot-execution-contract, a non-mutating readiness bridge after switch rehearsal that requires explicit gates, manual confirmation, fresh Rust-shadow data, and Python fallback before any future Rust collector authority pilot execution."
git push -u origin lqosync-in-rust
```


## Rust Core v4.3.1 hotfix commit

```bash
git add .
git commit -m "rust(core): fix pilot execution response recursion" \
  -m "Fix the collector authority pilot execution contract compile error by replacing the large serde_json json macro response with incremental serde_json Map construction while preserving fail-safe behavior."
git push -u origin lqosync-in-rust
```

## Rust Core v4.3.2 hotfix commit

```bash
git add .
git commit -m "rust(core): fix pilot execution confirmation gating" \
  -m "Fix collector authority pilot execution readiness by separating switch rehearsal confirmation from pilot execution confirmation while preserving non-mutating fail-safe behavior."
git push -u origin lqosync-in-rust
```


## v4.4 Commit Example

```bash
git add .
git commit -m "rust(core): add collector authority pilot result evaluator" \
  -m "Add evaluate-collector-authority-pilot-result, a non-mutating evaluator for pilot result readiness, parity, freshness, and forbidden side effects while keeping Python collectors authoritative."
git push -u origin lqosync-in-rust
```

## Rust Core v4.5 Collector Authority Promotion Readiness

```bash
git add .
git commit -m "rust(core): add collector authority promotion readiness" \
  -m "Add build-collector-authority-promotion-readiness, a non-mutating readiness bridge after pilot result evaluation that requires explicit gates, manual confirmation, fresh Rust-shadow data, and Python fallback before any future collector authority promotion."
git push -u origin lqosync-in-rust
```


## v4.6 collector authority promotion execution rehearsal

```bash
git add .
git commit -m "rust(core): add collector authority promotion execution rehearsal" \
  -m "Add build-collector-authority-promotion-execution-rehearsal, a non-mutating rehearsal bridge after promotion readiness that requires explicit gates, manual confirmation, fresh Rust-shadow data, and Python fallback while keeping production collector authority in Python."
git push -u origin lqosync-in-rust
```


## Rust Core v4.7 commit suggestion

```bash
git add .
git commit -m "rust(core): add collector authority promotion commit plan" \
  -m "Add build-collector-authority-promotion-commit-plan, a non-mutating commit-plan bridge after promotion execution rehearsal that requires explicit gates, manual confirmation, fresh Rust-shadow data, and Python fallback while keeping production collector authority in Python."
git push -u origin lqosync-in-rust
```


## Rust Core v4.9 commit suggestion

```bash
git add .
git commit -m "rust(core): add collector authority production freeze gate" \
  -m "Add build-collector-authority-production-freeze-gate, the final non-mutating pre-production freeze gate before a future Rust collector authority switch contract, requiring cutover readiness, manual confirmation, maintenance window, operator acknowledgment, rollback path, and Python fallback."
git push -u origin lqosync-in-rust
```


## v5.0 collector authority production switch contract

```bash
git add .
git commit -m "rust(core): add collector authority production switch contract" \
  -m "Add build-collector-authority-production-switch-contract, the first non-mutating production switch contract after the freeze gate while keeping Python backend and fallback required."
git push -u origin lqosync-in-rust
```


## Rust Core v5.1 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust backend API handoff plan" \
  -m "Add build-rust-backend-api-handoff-plan, the first full-Rust-backend-track bridge after collector authority production switch contract, preserving WebUI/UX and requiring Python backend fallback while route parity is prepared."
git push -u origin lqosync-in-rust
```


## Rust Core v5.2 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust backend scheduler handoff plan" \
  -m "Add build-rust-backend-scheduler-handoff-plan, the scheduler/run_cycle handoff bridge after API handoff while preserving WebUI/UX and keeping Python scheduler/run_cycle authoritative."
git push -u origin lqosync-in-rust
```


## Rust Core v5.3 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust run_cycle orchestrator handoff contract" \
  -m "Add build-rust-run-cycle-orchestrator-handoff-contract, the next full-Rust-backend bridge after scheduler handoff planning while keeping Python run_cycle authoritative and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v5.4 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust config state authority handoff contract" \
  -m "Add build-rust-config-state-authority-handoff-contract, the config/state authority handoff bridge after run_cycle orchestrator handoff while keeping Python config/state authoritative and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v5.5 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust live collector authority handoff contract" \
  -m "Add build-rust-live-collector-authority-handoff-contract, the live collector authority bridge after config/state handoff while keeping Python live collectors authoritative and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v5.6 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust circuit builder authority handoff contract" \
  -m "Add build-rust-circuit-builder-authority-handoff-contract, the circuit row/ShapedDevices builder authority bridge after live collector authority handoff while keeping Python backend fallback and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v5.7 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust sync engine authority handoff contract" \
  -m "Add build-rust-sync-engine-authority-handoff-contract, the sync engine authority bridge after circuit builder authority while keeping Python sync engine authoritative and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v5.8 commit suggestion

```bash
git add .
git commit -m "rust(core): add Rust apply journal rollback authority handoff contract" \
  -m "Add build-rust-apply-journal-rollback-authority-handoff-contract, the apply/journal/rollback authority bridge after sync engine authority while keeping Python backend fallback and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## v5.9 Rust backend service runtime handoff

```bash
git add .
git commit -m "rust(core): add Rust backend service runtime handoff contract" \
  -m "Add build-rust-backend-service-runtime-handoff-contract, the service/API runtime handoff bridge after apply/journal/rollback authority while keeping Python backend fallback and WebUI/UX unchanged."
git push -u origin lqosync-in-rust
```


## Rust Core v6.0 full Rust backend production readiness

```bash
git add .
git commit -m "rust(core): add full Rust backend production readiness contract" \
  -m "Add build-full-rust-backend-production-readiness-contract, the full backend readiness gate after service/runtime handoff while preserving WebUI/UX and requiring Python fallback until an explicit cutover/removal package."
git push -u origin lqosync-in-rust
```
