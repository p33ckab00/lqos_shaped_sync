# Rust Core v1.4 Transaction History and Rollback Plan Viewer

v1.4 adds read-only transaction history operations for the `lqosync-in-rust` branch.

## Purpose

v1.3 can append Rust transaction journal entries to:

```text
/opt/LQoSync/logs/transaction_journal.jsonl
```

v1.4 makes that journal operationally useful without introducing destructive rollback execution.

## New Rust operations

```text
read-transaction-journal
build-rollback-from-journal
```

Both operations are read-only.

## read-transaction-journal

Reads and filters transaction journal JSONL entries.

Request example:

```json
{
  "version": "1",
  "op": "read-transaction-journal",
  "payload": {
    "path": "/opt/LQoSync/logs/transaction_journal.jsonl",
    "limit": 50,
    "reverse": true,
    "include_event": true
  }
}
```

Supported filters:

```text
journal_id
manifest_id
transaction_status
sync_plan_verdict
executed
limit
offset
reverse
include_event
```

## build-rollback-from-journal

Selects a journal entry by `journal_id` or `manifest_id` and builds a rollback manifest from the embedded transaction result.

It does not restore files.

Request example:

```json
{
  "version": "1",
  "op": "build-rollback-from-journal",
  "payload": {
    "path": "/opt/LQoSync/logs/transaction_journal.jsonl",
    "journal_id": "txj-example"
  }
}
```

## WebUI/API endpoints

```text
GET /api/rust-core/transaction-journal
GET /api/rust-core/rollback-plan?journal_id=<id>
GET /api/rust-core/rollback-plan?manifest_id=<id>
```

These endpoints are read-only and require login.

## Safety model

```text
Python remains authoritative by default.
Rust rollback execution is not implemented in v1.4.
The rollback plan is preview-only.
Journal reading has Python fallback.
Invalid JSONL lines are surfaced as warnings, not silently ignored.
```

## Operator workflow

```text
1. Enable transaction journal persistence only when ready.
2. Run Dry Run / apply cycle.
3. Inspect /api/rust-core/transaction-journal.
4. Select a journal_id.
5. Inspect /api/rust-core/rollback-plan?journal_id=<id>.
6. Do not execute rollback automatically; v1.4 is preview-only.
```
