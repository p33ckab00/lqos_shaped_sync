# Rust Core v4.3.2 — Collector Authority Pilot Execution Confirmation Hotfix

## Purpose

Rust Core v4.3.1 compiled after the recursion fix, but the ready-state self-test still failed because the collector authority pilot execution contract used one root `confirmation` field for two different stages:

- switch rehearsal confirmation: `CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL`
- pilot execution confirmation: `CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION`

The pilot execution stage overwrote the root confirmation value, so the nested switch rehearsal rebuilt itself as `shadow_only` instead of `collector_authority_switch_rehearsal_ready`.

## Fix

v4.3.2 adds support for a separate switch confirmation input:

```json
{
  "confirmation": "CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION",
  "collector_authority_switch_confirmation": "CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"
}
```

The Rust core uses `collector_authority_switch_confirmation` only when it must internally rebuild the prerequisite switch rehearsal. If a prebuilt `collector_authority_switch_rehearsal` result is provided, that object remains authoritative for the prerequisite check.

## Safety

No production authority is changed. This remains a non-mutating contract-only phase.

- No live RouterOS reads
- No collector authority switch
- No cleanup authority transfer
- No generated file writes
- No LibreQoS apply authority
- Python collector fallback remains mandatory

## Versions

- LQoSync `2.113.2-rc1`
- Rust core `4.3.2`
