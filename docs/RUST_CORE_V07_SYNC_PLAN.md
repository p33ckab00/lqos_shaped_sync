# Rust Core v0.7 Sync Plan Shadow Engine

Version: `2.77.0-rc1`  
Rust crate: `lqosync-core 0.7.0`

## Purpose

v0.7 adds a shadow-only end-to-end sync planner. The planner combines the Rust/Python diagnostics already produced by previous milestones:

```text
collector trust
+ Rust diff
+ Rust circuit shadow
+ Rust validation
+ Rust policy shadow
+ Python preflight
+ cleanup stats
= Rust sync plan shadow
```

Python remains authoritative. The Rust plan does not write files, delete rows, or trigger LibreQoS apply.

## New operation

```text
evaluate-sync-plan
```

Request envelope:

```json
{
  "version": "1",
  "op": "evaluate-sync-plan",
  "payload": {
    "mode": "dry_run",
    "files_changed": true,
    "csv_changed": true,
    "network_changed": false,
    "rust_diff": {},
    "rust_validation": {},
    "rust_policy_shadow": {},
    "rust_circuit_shadow": {},
    "collector_trust": [],
    "preflight": {},
    "cleanup": {}
  }
}
```

Response result:

```json
{
  "mode": "shadow",
  "authoritative": false,
  "verdict": "ready_by_shadow_plan",
  "risk_score": 0,
  "risk_level": "low",
  "write_allowed": false,
  "apply_allowed": false,
  "cleanup_allowed": true,
  "summary": {},
  "blockers": [],
  "holds": [],
  "next_actions": [],
  "decision_trace": []
}
```

## Verdicts

| Verdict | Meaning |
|---|---|
| `ready_by_shadow_plan` | No Rust shadow blocker was found and files changed. |
| `manual_review_recommended` | The Rust plan found holds or medium/high risk. |
| `blocked_by_shadow_plan` | Rust validation/preflight/policy/circuit shadow found blockers. |
| `no_changes` | No generated file change is needed. |

## Safety rule

Even when Rust returns `write_allowed=true` or `apply_allowed=true`, Python remains the authority in v0.7. These booleans are only planning hints for future migration.

## Dry Run UI

Dry Run now shows a **Rust Sync Plan Shadow** card with:

- verdict
- risk score/risk level
- blocker count
- hold count
- shadow mode
- raw JSON details

## Next migration step

After v0.7, the next controlled milestone should be either:

```text
v0.8 Rust Apply Guard Authority (optional/enforced only when explicitly enabled)
```

or

```text
v0.8 Rust Circuit Builder Parity Tests
```

Do not make Rust authoritative until shadow output matches Python behavior across real production dry-runs.
