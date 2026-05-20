# Rust Core v1.3 Transaction Journal Persistence

Rust Core v1.3 adds an opt-in `append-transaction-journal` protocol operation. It turns the v1.2 journal preview into a persistable JSONL event while keeping default behavior rehearsal-only.

## Purpose

The goal is to make future Rust apply authority auditable before broader Rust write/apply controls are enabled. A transaction that writes files can now produce a durable journal event that records the apply manifest, transaction result, sync-plan verdict, and rollback availability.

Canonical path:

```text
/opt/LQoSync/logs/transaction_journal.jsonl
```

## New operation

```text
append-transaction-journal
```

Safety flags:

```json
{
  "append": false,
  "allow_journal_write": false,
  "include_rehearsal_entries": false,
  "allow_dry_run_journal": false
}
```

Default result is rehearsal-only. No file is written unless `append=true` and `allow_journal_write=true`. Dry Run still does not write unless `allow_dry_run_journal=true`.

## Config flags

```json
"rust_core": {
  "append_transaction_journal": false,
  "allow_transaction_journal_writes": false,
  "include_rehearsal_journal_entries": false,
  "allow_dry_run_journal_entries": false
}
```

Recommended production default is all false until Rust transaction execution is intentionally enabled and tested.

## Dry Run visibility

Dry Run now shows the Rust transaction journal append status beside the journal and rollback previews. Typical statuses:

```text
rehearsal_only
not_allowed
dry_run_preview_only
not_required
appended
failed
```

## Safety model

- Python remains authoritative by default.
- Rust journal append is opt-in.
- Python fallback never writes the transaction journal if Rust is unavailable.
- The event is JSONL and can be inspected independently from normal audit logs.

## Test commands

```bash
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
sudo scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```
