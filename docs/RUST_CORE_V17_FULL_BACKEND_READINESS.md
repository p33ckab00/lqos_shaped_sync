# Rust Core v1.7 Full Backend Readiness + Authority Pilot Plan

Version: LQoSync 2.87.0-rc1 / lqosync-core 1.7.0

This release adds a read-only bridge between the current hybrid architecture and a future full Rust backend.

## Important status

LQoSync is **not yet a full Rust backend**.

Current model:

```text
Python Flask WebUI / scheduler / run_cycle / RouterOS collectors = authoritative by default
Rust core = safety, validation, planning, transaction, journal, rollback, and optional authority gates
```

The Rust core is mature enough for authority pilots, but several production responsibilities still remain in Python:

- Flask WebUI, auth, routes, templates
- scheduler runner
- `engine/run_cycle.py` orchestration
- RouterOS API collectors
- final external LibreQoS.py apply runner
- service monitor, docs, reports, notification UI

## New Rust operations

```text
evaluate-full-rust-readiness
build-authority-pilot-plan
```

Both are read-only. They do not write files, run LibreQoS, restore backups, or mutate config.

## New API endpoints

```text
GET /api/rust-core/full-backend-readiness
GET /api/rust-core/authority-pilot-plan
```

## Full backend readiness verdict

The expected verdict in this release is:

```text
not_full_rust_backend_yet
```

This is intentional. It tells the operator that Rust has strong backend safety capabilities, but the application is still a controlled hybrid system.

## Authority pilot stages

The authority pilot plan returns staged, explicit config deltas:

1. Shadow baseline
2. Daemon and self-test
3. Sync-plan enforcement
4. Transaction journal persistence
5. Rust file-write pilot
6. Rollback execution pilot
7. Collector/circuit migration

Recommended guardrail:

```text
Do not enable Rust file-write authority until transaction journal persistence is enabled and multiple clean dry-runs/sync cycles have passed.
```

## What this prevents

This release prevents calling the project a full Rust backend too early. It makes the remaining Python-owned responsibilities visible and gives operators a staged bridge toward Rust authority.
