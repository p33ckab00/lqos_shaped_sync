# Rust Core v7.5.2 — Stale Codebase Cleanup Guard

v7.5.2 adds a safe, operator-controlled cleanup layer for stale codebases and legacy runtime remnants after the full Rust backend production series.

This is intentionally **verification-first** and **archive-first**. It does not blindly delete Python, Flask, old working trees, old Docker containers, or WebUI assets.

## Scope

The cleanup guard helps identify and classify:

- duplicate working copies such as `/home/pi/lqosync_docker` after `/opt/LQoSync` becomes canonical
- old lowercase installs such as `/opt/lqosync`
- legacy Python service processes such as Gunicorn/Flask backends
- legacy Docker containers such as old sync containers
- old service files and timers that may restart retired code
- stale Python modules in the repository that are kept only for rollback or documentation compatibility

## Canonical paths

| Component | Canonical value |
|---|---|
| App/repository path | `/opt/LQoSync` |
| Git branch | `lqosync-in-rust` |
| Rust binary | `/usr/local/bin/lqosync-core` |
| Rust service | `lqosync-core.service` |
| Rust socket | `/run/lqosync-core.sock` |
| LibreQoS source path | `/opt/libreqos/src` |

## Safety rules

The cleanup guard follows these rules:

1. Keep `/opt/LQoSync` as the canonical app directory.
2. Keep `/opt/libreqos` untouched.
3. Keep `/usr/local/bin/lqosync-core` and `lqosync-core.service` untouched.
4. Do not delete WebUI/UX/static assets.
5. Do not delete Python code until rollback requirements are explicitly satisfied.
6. Archive stale working copies before deletion.
7. Never stop or disable services by default.
8. Require explicit confirmation before moving old directories into an archive.

## New scripts

```bash
scripts/stale-codebase-inventory.sh
scripts/stale-codebase-cleanup-dry-run.sh
scripts/stale-codebase-archive-executor-guard.sh
```

### Inventory

```bash
bash scripts/stale-codebase-inventory.sh
```

This prints services, processes, ports, Docker containers, timers, candidate paths, and Git metadata relevant to LQoSync cleanup.

### Dry run

```bash
bash scripts/stale-codebase-cleanup-dry-run.sh
```

This proposes actions but does not mutate anything.

### Archive executor

Archive is guarded and opt-in:

```bash
export CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE
sudo -E bash scripts/stale-codebase-archive-executor-guard.sh --execute
```

The executor only archives safe candidate directories such as duplicate working trees. It does not touch the canonical `/opt/LQoSync` install.

## Classification

| Class | Meaning | Default action |
|---|---|---|
| keep | Canonical or required runtime | no action |
| archive-candidate | likely stale duplicate or old working tree | dry-run only unless confirmed |
| inspect | needs operator decision | no action |
| never-delete | critical path or external dependency | no action |

## Recommended cleanup flow

```bash
bash scripts/stale-codebase-inventory.sh
bash scripts/stale-codebase-cleanup-dry-run.sh

# Review output carefully first.
export CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE
sudo -E bash scripts/stale-codebase-archive-executor-guard.sh --execute

bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

## Production note

v7.5.2 does not add a new Rust core operation. It is an operational cleanup package for stale codebase visibility and safe archiving after v7.5 audit sentinel readiness.
