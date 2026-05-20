# Rust Core v3.9 — run_cycle Rust-Shadow Integration Report

Rust Core v3.9 adds `build-run-cycle-rust-shadow-report`, a non-mutating bridge that lets the Python `run_cycle` attach Rust-shadow collector dry-run data beside the authoritative Python collector result.

## Purpose

This phase prepares the production orchestrator for the future Rust collector authority pilot without switching authority yet. It answers:

- Is a Rust-shadow collector bundle available for this cycle?
- How many authoritative Python rows and Rust-shadow rows are present?
- Is parity available?
- Can Rust output drive cleanup or apply? In v3.9, always no.

## Safety model

Python remains authoritative. Rust does not perform live RouterOS reads, does not drive cleanup, does not write generated files, and does not run LibreQoS apply.

The report always returns:

```text
python_run_cycle_authoritative = true
rust_can_drive_cleanup = false
rust_can_drive_apply = false
rust_can_write_generated_files = false
full_rust_backend = false
```

## Operation

```json
{
  "op": "build-run-cycle-rust-shadow-report",
  "version": "1",
  "payload": {
    "python_rows": [],
    "collector_parity": {"parity_score": 100, "verdict": "parity_pass"}
  }
}
```

## Config flags

```json
"rust_core": {
  "run_cycle_rust_shadow_report_enabled": false,
  "run_cycle_rust_shadow_report_pilot": false,
  "run_cycle_rust_shadow_include_rows": false
}
```

The default is disabled. When enabled, the report is still diagnostic-only.

## New API

```text
GET  /api/rust-core/run-cycle-rust-shadow-report
POST /api/rust-core/run-cycle-rust-shadow-report
```

## Next phase

The next safe phase is run_cycle UI/report visibility and then Rust collector authority pilot integration, where Rust-shadow rows can be compared continuously before any source becomes Rust-authoritative.
