# Rust Core v3.8 Collector Authority Dry-Run Bundle

This release adds `build-collector-authority-dry-run-bundle`.

It combines the v3.7 collector authority dry-run source selection with a Rust-shadow collector bundle and a parity report. It is intended for operator visibility and future run-cycle integration only.

## Safety

Python collectors remain production-authoritative. Rust-shadow rows cannot drive cleanup, generated file writes, or LibreQoS apply in this phase.

The operation reports:

- `collector_authority = python_authoritative`
- `collector_output_can_drive_cleanup = false`
- `collector_output_can_drive_apply = false`
- `python_collector_fallback_required = true`
- `full_rust_backend = false`

## Operation

```text
build-collector-authority-dry-run-bundle
```

## API

```text
GET  /api/rust-core/collector-authority-dry-run-bundle
POST /api/rust-core/collector-authority-dry-run-bundle
```

## Required gates for Rust-shadow bundle readiness

```json
{
  "rust_core": {
    "collector_authority_dry_run_selection_pilot": true,
    "allow_collector_authority_dry_run_selection": true,
    "collector_authority_dry_run_bundle_pilot": true,
    "allow_collector_authority_dry_run_bundle": true
  }
}
```

These gates only permit shadow comparison. They do not transfer authority.

## Next phase

The next phase is run-cycle integration where Python can display Rust-shadow dry-run bundle results beside Python-authoritative collector output.
