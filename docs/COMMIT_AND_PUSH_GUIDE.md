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
