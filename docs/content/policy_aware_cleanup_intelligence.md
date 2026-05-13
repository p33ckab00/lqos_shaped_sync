# Policy-Aware Cleanup Intelligence

LQoSync v2.50 extends Smart Policy Center with deeper policy intelligence while keeping operator control in `config.json -> policies`.

## What changed

- Added optional source-aware stale lifecycle settings.
- Added optional grace-run behavior for normal inactive cleanup.
- Added risk-aware LibreQoS auto-apply policy.
- Added policy decision trace entries so operators can see which policies influenced cleanup/apply behavior.
- Added cleanup queue seen-run tracking so next-run/grace cleanup can be reasoned about across sync cycles.

## Stale lifecycle and grace

Grace is optional and disabled by default per source. It should only be enabled when identity is stable.

Recommended use:

```text
PPPoE username        -> grace can be useful
Hotspot username      -> grace can be useful if voucher/username is stable
DHCP randomized MAC   -> grace is risky and should stay disabled
```

If grace is enabled for a source, normal inactive rows are queued until they have been missing for the configured number of consecutive runs. If the same client identity returns before cleanup, Smart Lifecycle records a returned-client event and active state resumes.

## Risk-aware auto apply

`policies.auto_apply_policy` decides whether LibreQoS.py may run automatically by risk level:

```json
{
  "enabled": true,
  "allow_low_risk": true,
  "allow_medium_risk": false,
  "allow_high_risk": false,
  "allow_critical_risk": false,
  "when_blocked": "keep_pending_manual_apply"
}
```

If files are written but risk-aware auto apply does not allow the current risk level, LQoSync keeps the LibreQoS apply pending for operator review. This gives fast automatic apply for low-risk changes while preventing medium/high-risk changes from silently applying.

## Decision trace

Policy decisions now include a `decision_trace` list. It explains rules like:

```text
cleanup_next_run queued a client
optional stale lifecycle required N missing runs
auto apply was allowed or held by risk policy
source cleanup guard triggered
confirmation required
```

The trace is intended for Dashboard, Dry Run, logs, and troubleshooting.
