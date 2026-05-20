Ito ang **full handoff documentation** ng napag-usapan natin para i-copy paste mo sa original branch/chat na may full project context.

````markdown
# LQoSync Smart / Intelligent Policy Center — Full Implementation Handoff

## Important instruction

Do not blindly apply any patch pack from a branch-off conversation. The correct implementation must be done directly inside the latest full LQoSync project tree / original branch.

This document contains the full agreed design, logic, UI/UX behavior, policy model, cleanup rules, smart decision engine, and roadmap.

Target next release:

LQoSync v2.45 Smart Policy Center

Core goal:

LQoSync should not just sync MikroTik data to LibreQoS. It should observe, decide, explain, protect, and recommend.

---

# 1. Core philosophy

LQoSync should become a smart operator system.

Current/simple behavior:

```text
Collect MikroTik data
Generate ShapedDevices.csv
Generate network.json
If changed, run LibreQoS.py --updateonly
````

Target smart behavior:

```text
Collect MikroTik data
Classify source health
Build proposed output
Compare current vs proposed
Classify removals and changes
Run policy engine
Calculate risk
Decide:
  allow
  warn
  cleanup immediately
  cleanup next run
  require confirmation
  block cleanup
  block apply
Explain the decision in Dashboard and Dry Run
Apply only if safe under operator policies
```

Important principle:

```text
Config = operator intent
Policies = safety rules
Policy engine = decision maker
Dashboard / Dry Run = explanation layer
```

The system should not be blind. All smart behaviors must be visible in Settings / Config Center through a Policy Center UI.

---

# 2. Why policies are needed

Example:

Operator disables PPPoE because they only want DHCP and Hotspot.

Result:

```text
Existing PPP rows = 35
PPP collector disabled
Proposed PPP rows = 0
Removal = 100%
```

A naive mass-removal guard would think this is dangerous and block it.

But in reality:

```text
PPP disabled by operator = intentional config change
PPP API failed = unintentional failure
PPP returned zero while enabled = suspicious
```

These must be treated differently.

Therefore:

```text
Detection is not deletion.
The system may detect stale rows, but cleanup policy decides what to do.
```

---

# 3. Main Policy Center concept

Create a visible Policy Center module in Settings / Config Center.

Recommended modules:

```text
Policy Center
├─ Policy Preset
├─ Cleanup Policies
├─ Source Lifecycle Policies
├─ Apply Guard Policies
├─ Collector Guard Policies
├─ Mass Change Guard Policies
├─ Data Quality Policies
├─ Topology Guard Policies
├─ Backup Guard Policies
├─ Anomaly Detection Policies
└─ Recommendations
```

Each policy card should show:

```text
Policy name
Enabled / disabled
Threshold value
Action when triggered
Why this matters
Recommended setting
Current effective value
```

Do not hide these in raw JSON only.

Raw JSON editor can remain available for advanced users.

---

# 4. Suggested config structure

Use this as a recommended config model. Adjust names based on existing project style.

```json
{
  "policies": {
    "mode": "balanced",

    "cleanup": {
      "enabled": true,

      "global_default_action": "require_confirm_next_run",

      "confirmation_expires_hours": 24,
      "apply_confirmed_cleanup": "next_run",

      "normal_inactive_default_action": "cleanup_next_run",
      "source_disabled_default_action": "require_confirm_next_run",
      "collector_failed_default_action": "preserve_rows",
      "source_zero_result_default_action": "block_cleanup",

      "allow_immediate_cleanup": true
    },

    "cleanup_sources": {
      "pppoe": {
        "enabled": true,
        "normal_inactive_action": "cleanup_next_run",
        "source_disabled_action": "require_confirm_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "block_cleanup",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": true
      },
      "dhcp": {
        "enabled": true,
        "normal_inactive_action": "cleanup_immediate",
        "source_disabled_action": "require_confirm_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "block_cleanup",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": false
      },
      "hotspot": {
        "enabled": true,
        "normal_inactive_action": "cleanup_immediate",
        "source_disabled_action": "cleanup_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "warn_only",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": false
      },
      "static": {
        "enabled": true,
        "normal_inactive_action": "preserve_rows",
        "source_disabled_action": "preserve_rows",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "preserve_rows",
        "mass_removal_action": "preserve_rows",
        "respect_percentage_guards": true
      }
    },

    "node_cleanup_guard": {
      "enabled": true,
      "threshold_percent": 30,
      "min_node_size": 10,
      "min_removed_count": 3,
      "action": "require_confirm_next_run"
    },

    "small_node_guard": {
      "enabled": true,
      "max_node_size": 5,
      "partial_removal_action": "cleanup_next_run",
      "full_removal_action": "require_confirm_next_run"
    },

    "source_cleanup_guard": {
      "enabled": true,
      "threshold_percent": 30,
      "min_removed_count": 5,
      "action": "require_confirm_next_run"
    },

    "apply_guard": {
      "block_apply_on_collector_failure": true,
      "block_apply_on_missing_parent": true,
      "block_apply_on_duplicate_ip": true,
      "block_apply_on_invalid_speed": true,
      "require_manual_confirm_on_medium_risk": true,
      "allow_auto_apply_on_low_risk": true
    },

    "collector_guard": {
      "block_cleanup_if_source_failed": true,
      "block_cleanup_if_enabled_source_returns_zero": true,
      "block_cleanup_if_source_returns_zero_after_previous_success": true,
      "zero_source_drop_threshold_percent": 80,
      "warn_if_router_api_slow_ms": 2000
    },

    "data_quality": {
      "warn_on_fallback_speed": true,
      "fallback_speed_warning_threshold_percent": 10,
      "block_if_fallback_speed_threshold_percent": 50,
      "warn_on_missing_mac": true,
      "warn_on_missing_ip": true
    },

    "topology_guard": {
      "block_missing_parent_nodes": true,
      "block_duplicate_node_names": true,
      "warn_on_virtual_node_promotion": true,
      "warn_on_deep_hierarchy_depth": true,
      "max_recommended_depth": 4
    },

    "backup_guard": {
      "require_backup_before_apply": true,
      "warn_if_backup_disabled_while_auto_apply_enabled": true,
      "minimum_backup_retention": 30
    },

    "anomaly_detection": {
      "enabled": true,
      "compare_with_last_successful_run": true,
      "warn_if_client_count_drops_percent": 30,
      "warn_if_sync_duration_increases_multiplier": 5,
      "warn_if_apply_duration_increases_multiplier": 5
    },

    "recommendations": {
      "enabled": true,
      "show_why_fix_messages": true,
      "show_operator_next_action": true
    }
  }
}
```

---

# 5. Supported cleanup actions

The cleanup system must support these actions:

```text
preserve_rows
warn_only
cleanup_immediate
cleanup_next_run
require_confirm_immediate
require_confirm_next_run
block_cleanup
block_apply
```

Meanings:

## preserve_rows

Keep old rows. No deletion.

## warn_only

Show warning but do not delete.

## cleanup_immediate

Delete rows in the same sync cycle.

## cleanup_next_run

Mark rows for cleanup, then delete on the next successful sync run.

## require_confirm_immediate

Operator must confirm; after confirmation, cleanup can happen immediately.

## require_confirm_next_run

Operator must confirm; after confirmation, cleanup applies on the next successful sync run.

Recommended production default for risky cases.

## block_cleanup

Do not delete. Keep files safe.

## block_apply

Block LibreQoS apply. Used for dangerous validation failures.

---

# 6. Cleanup reason classification

Every removed/stale row must be classified before applying policy.

Reasons:

```text
normal_inactive
source_disabled
collector_failed
source_zero_result
mass_removal
manual_excluded
topology_policy
duplicate_policy
```

Important distinction:

```text
PPP disabled intentionally ≠ PPP API failed
DHCP source returned zero while enabled ≠ DHCP server disabled by operator
One client inactive ≠ node/source mass removal
```

Policy engine must decide based on reason.

---

# 7. Source lifecycle behavior

Each source should be handled independently:

```text
PPP / PPPoE
DHCP
Hotspot
Static/manual rows
```

Example behavior:

```text
PPP normal inactive      → cleanup_next_run
DHCP normal inactive     → cleanup_immediate
Hotspot normal inactive  → cleanup_immediate

PPP disabled             → require_confirm_next_run
DHCP server disabled     → require_confirm_next_run
Hotspot disabled         → cleanup_next_run

Collector failed         → preserve_rows
Zero result while enabled → block_cleanup or require_confirm_next_run
```

This gives the operator full freedom.

---

# 8. Immediate vs next-run cleanup

Operator must be able to choose per source:

```text
cleanup immediately
cleanup next run
require confirmation then cleanup immediately
require confirmation then cleanup next run
preserve rows
warn only
block cleanup
```

Example:

```text
DHCP normal inactive = cleanup_immediate
PPP normal inactive = cleanup_next_run
Hotspot normal inactive = cleanup_immediate
```

This supports fast / effective updates when the operator wants immediate behavior.

Tradeoff warning:

If cleanup is immediate and clients flap:

```text
client disappears → row removed → LibreQoS apply
client returns → row added → LibreQoS apply again
```

Optional anti-flap setting can be added later:

```json
{
  "anti_flap": {
    "enabled": true,
    "minimum_apply_interval_seconds": 30,
    "coalesce_changes": true
  }
}
```

---

# 9. Per-source override precedence

Policy precedence should be predictable.

Recommended order:

```text
1. Hard safety rules
2. Per-server / per-profile override
3. Per-source policy
4. Global cleanup policy
5. Default fallback
```

Example:

```text
DHCP-LAN has custom cleanup policy
→ use DHCP-LAN policy

No DHCP-LAN override
→ use DHCP source policy

No DHCP policy
→ use global cleanup policy
```

Optional future model:

```json
{
  "dhcp_server_overrides": {
    "LAN": {
      "normal_inactive_action": "cleanup_next_run"
    },
    "Wifi5Soft": {
      "normal_inactive_action": "cleanup_immediate"
    }
  }
}
```

---

# 10. Small node handling

Percentage-only cleanup guards are dangerous for small nodes.

Example:

```text
DHCP node before: 3 clients
Removed: 1 client
Removal percent: 33.33%
Threshold: 30%
```

Naive result:

```text
Block deletion
```

But this is too sensitive because only one client disappeared.

Correct logic:

```text
Apply percentage guard only if:
removed_percent >= threshold_percent
AND removed_count >= min_removed_count
AND previous_node_count >= min_node_size
```

Recommended policy:

```json
{
  "node_cleanup_guard": {
    "enabled": true,
    "threshold_percent": 30,
    "min_node_size": 10,
    "min_removed_count": 3,
    "action": "require_confirm_next_run"
  }
}
```

So:

```text
Before: 3
Removed: 1
Percent: 33%

But:
node size < 10
removed count < 3

Result:
Do not block.
Treat as small-node normal cleanup.
```

Small node policy:

```json
{
  "small_node_guard": {
    "enabled": true,
    "max_node_size": 5,
    "partial_removal_action": "cleanup_next_run",
    "full_removal_action": "require_confirm_next_run"
  }
}
```

Recommended rule:

```text
Use percentage only for medium/large nodes.
Use absolute count/grace behavior for small nodes.
Require confirmation for full-node removal, even if small.
```

---

# 11. Node / source / global cleanup guards

There should be multiple guard layers:

```text
1. Per-client normal inactive cleanup
2. Per-node removal guard
3. Per-source removal guard
4. Global mass-removal guard
```

Per-node example:

```text
Node: DHCP-LAN
Before: 100
Removed: 35
Removal percent: 35%
Policy: threshold 30%
Result: require confirmation / block
```

Per-source example:

```text
DHCP total before: 80
DHCP total after: 10
Removed: 70
Result: block or require confirmation
```

Global example:

```text
All generated clients before: 300
All generated clients after: 100
Removed: 200
Result: critical risk
```

---

# 12. Pending confirmation system

If policy action is:

```text
require_confirm_next_run
```

then system should create a pending confirmation.

Suggested runtime state:

```json
{
  "pending_confirmations": [
    {
      "id": "cleanup-pppoe-RB5k9-Distro-20260513",
      "type": "cleanup_confirmation",
      "source": "pppoe",
      "router": "RB5k9-Distro",
      "reason": "source_disabled",
      "affected_rows": 35,
      "apply_mode": "next_run",
      "scope_hash": "abc123",
      "config_hash": "def456",
      "created_by": "admin",
      "created_at": "2026-05-13T10:00:00+08:00",
      "expires_at": "2026-05-14T10:00:00+08:00",
      "confirmed": true
    }
  ]
}
```

Important:

Confirmation must be specific.

Not enough:

```text
Yes, delete
```

Required:

```text
Confirm PPP cleanup
Source: PPPoE
Router: RB5k9-Distro
Rows affected: 35
Reason: PPPoE collector disabled
Apply mode: next run
Expires: 24h
```

If config changes after confirmation:

```text
Confirmation invalidated.
Please confirm cleanup again.
```

---

# 13. Source disabled cleanup flow

Example:

Before:

```text
PPP enabled
PPP rows: 35
```

Operator changes config:

```text
pppoe.enabled = false
```

Dry run / scheduler detects:

```text
PPP source disabled.
35 existing PPP rows would be removed.
```

Policy:

```text
source_disabled_action = require_confirm_next_run
```

System result:

```text
No cleanup yet.
No apply yet if cleanup is the only change.
Dashboard shows pending confirmation.
```

UI:

```text
Pending Cleanup Confirmation

PPP source disabled
35 PPP rows are pending removal

Policy:
require_confirm_next_run

Action:
Confirm cleanup or re-enable PPP collector
```

After operator confirms:

```text
Confirmation saved.
PPP rows will be removed on the next successful sync run.
```

Next run:

```text
Valid confirmation found.
PPP cleanup applied.
ShapedDevices.csv changed.
LibreQoS apply triggered if auto_apply allowed.
```

---

# 14. Collector failure behavior

If source is enabled but collector fails:

```text
pppoe.enabled = true
PPP API failed
```

This is not operator intent.

Recommended behavior:

```text
preserve old PPP rows
block cleanup for PPP
possibly block apply if proposed output is unsafe
show warning/error
```

Policy:

```json
{
  "collector_failed_action": "preserve_rows"
}
```

Dashboard:

```text
PPP collector failed.
PPP cleanup blocked.
Old PPP rows preserved.

Reason:
Source is enabled but API read failed.

Recommended action:
Check MikroTik API, credentials, firewall, or router availability.
```

---

# 15. Zero result behavior

If source is enabled and scan succeeds but returns zero:

```text
DHCP enabled
DHCP scan OK
valid leases = 0
last successful DHCP count = 42
```

This is suspicious.

Recommended default:

```text
block_cleanup
```

or:

```text
require_confirm_next_run
```

Policy:

```json
{
  "zero_result_action": "block_cleanup"
}
```

Dashboard:

```text
DHCP returned zero active rows.
Previous successful scan had 42.
Cleanup blocked to prevent accidental mass deletion.
```

---

# 16. Dry Run Verdict

Dry Run should classify result:

```text
Safe to apply
Apply with caution
Requires confirmation
Blocked by policy
```

Examples:

## Safe

```text
Dry Run Verdict: Safe to apply

Changes:
1 client added
0 removed
0 duplicate IPs
0 missing parent nodes
No collector failure
```

## Requires confirmation

```text
Dry Run Verdict: Requires confirmation

PPP source disabled.
35 PPP rows would be removed.

Policy:
require_confirm_next_run

Next action:
Confirm PPP cleanup or re-enable PPP.
```

## Blocked

```text
Dry Run Verdict: Blocked by policy

Reasons:
- DHCP source returned zero rows after previous successful scan
- 3 missing parent nodes
- duplicate IP detected

No files were written.
LibreQoS will not be applied.
```

---

# 17. Dashboard Policy Decision Card

Dashboard should show:

```text
Policy Decision

Status:
Allowed / Warn / Requires confirmation / Blocked

Risk:
Low / Medium / High / Critical

Triggered policies:
- Source Lifecycle: PPP disabled
- Cleanup Guard: 35 rows pending removal
- Apply Guard: confirmation required

Next action:
Confirm cleanup / Run dry-run / Fix config / Re-enable source
```

Example:

```text
Cleanup Decision

Node: DHCP-LAN-RB5k9-Distro
Before: 3 clients
After: 2 clients
Removed: 1 client
Removal percent: 33.3%

Policy result:
Allowed as small-node normal cleanup.

Reason:
Node size is below minimum threshold of 10 clients,
and removed count is below minimum count of 3.

Action:
Mark stale and cleanup on next run.
```

---

# 18. Recommendations panel

Add Dashboard / Policy Center recommendations.

Examples:

```text
Recommended Actions

1. Confirm PPP cleanup
Reason: PPP source is disabled and 35 rows are pending removal.

2. Review fallback-speed clients
Reason: 2 clients used global default speed.

3. Enable backup_before_apply
Reason: auto_apply is enabled but backups are disabled.

4. Update available
Reason: GitHub version is newer.

5. Check DHCP source
Reason: DHCP returned zero rows after previous successful scan.
```

Each recommendation should have:

```text
Title
Reason
Suggested action
Severity
Link/button
```

---

# 19. Risk score

Policy engine should output:

```json
{
  "risk_score": 0,
  "risk_level": "low"
}
```

Suggested levels:

```text
0–20    Low
21–50   Medium
51–80   High
81–100  Critical
```

Risk inputs:

```text
collector failure
source zero result
mass removal
missing parent nodes
duplicate IPs
invalid speed
fallback speed percentage
backup disabled while auto_apply enabled
LibreQoS previous apply failed
file drift
```

Result example:

```text
Risk: High

Reasons:
- 42% of clients would be removed
- DHCP scan returned zero rows
- 3 missing parent nodes
```

---

# 20. Apply guard before file write/apply

Important design:

Policy engine must run before final file write and LibreQoS apply.

Flow:

```text
1. Load config
2. Load existing ShapedDevices.csv and network.json
3. Collect MikroTik sources
4. Build proposed ShapedDevices.csv and network.json
5. Diff existing vs proposed
6. Classify cleanup/removals
7. Validate proposed data
8. Evaluate policies
9. Decide:
   - write allowed?
   - cleanup allowed?
   - apply allowed?
   - confirmation required?
10. Only then write files / apply LibreQoS
```

Do not write dangerous output first and block later.

---

# 21. Policy result object

Suggested policy evaluation output:

```json
{
  "verdict": "requires_confirmation",
  "risk_score": 72,
  "risk_level": "high",
  "apply_allowed": false,
  "write_allowed": false,
  "cleanup_allowed": false,
  "requires_confirmation": true,
  "confirmation_items": [],
  "blocked_reasons": [],
  "warnings": [],
  "recommendations": [],
  "cleanup_decisions": [],
  "triggered_policies": []
}
```

Possible verdicts:

```text
safe_to_apply
apply_with_caution
requires_confirmation
blocked_by_policy
dry_run_only
```

---

# 22. Policy Center UI details

Suggested UI layout:

```text
Config Center → Policy Center

[Preset Mode]
Conservative / Balanced / Aggressive / Custom

[Cleanup Policies]
Global default action
Confirmation expiry
Apply confirmed cleanup: immediate / next run

[PPP Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[DHCP Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[Hotspot Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[Node Cleanup Guard]
Threshold percent
Minimum node size
Minimum removed count
Action

[Small Node Guard]
Max small node size
Partial removal action
Full removal action

[Apply Guard]
Block duplicate IP
Block missing parent
Block invalid speed
Block collector failure

[Recommendations]
Show why/fix messages
Show next action
```

Each dropdown should include:

```text
Preserve rows
Warn only
Cleanup immediately
Cleanup on next run
Require confirmation then cleanup immediately
Require confirmation then cleanup next run
Block cleanup
Block apply
```

---

# 23. Preset modes

Add presets to simplify the UI.

## Conservative

Best for production / live ISP.

```text
More blocking
More confirmations
Lowest risk
```

Suggested behavior:

```text
PPP normal inactive: cleanup_next_run
DHCP normal inactive: cleanup_next_run
Hotspot normal inactive: cleanup_next_run
Source disabled: require_confirm_next_run
Collector failed: preserve_rows
Zero result: block_cleanup
Mass removal: require_confirm_next_run
Respect guards: true
```

## Balanced

Recommended default.

```text
Blocks dangerous changes
Allows normal operations
```

Suggested behavior:

```text
PPP normal inactive: cleanup_next_run
DHCP normal inactive: cleanup_next_run
Hotspot normal inactive: cleanup_immediate
Source disabled: require_confirm_next_run
Collector failed: preserve_rows
Zero result: block_cleanup
Mass removal: require_confirm_next_run
```

## Aggressive

For lab/testing or highly dynamic environments.

```text
Fast apply
Fewer blocks
More operator responsibility
```

Suggested behavior:

```text
PPP normal inactive: cleanup_immediate
DHCP normal inactive: cleanup_immediate
Hotspot normal inactive: cleanup_immediate
Source disabled: cleanup_next_run or require_confirm_next_run
Collector failed: preserve_rows
Zero result: warn_only or cleanup_next_run
Respect guards: optional
```

## Custom

Operator controls everything manually.

---

# 24. Smart warning format

Every warning should answer:

```text
What happened?
Why it matters?
What should I do?
```

Example:

```text
Some clients used fallback speed.

What happened:
3 PPPoE clients did not match speed from secret comment, active comment, profile comment, profile name, or rate-limit.

Why it matters:
They were assigned the default speed, which may be incorrect.

Recommended action:
Add speed to PPP secret comment or profile name.
```

---

# 25. Speed resolver diagnostics

For each client, optionally show resolver path.

Example PPP:

```text
Speed Resolution Path

1. PPP secret comment       empty
2. PPP active comment       empty
3. PPP profile comment      empty
4. PPP profile name         Tier-15M → matched
5. PPP profile rate-limit   not used
6. Default                  not used

Resolved speed: 15/15 Mbps
```

Example DHCP:

```text
1. DHCP server speed_comment   empty
2. DHCP server name            LAN → parsed 15M
3. DHCP server config speed    not used
4. Global default              not used

Resolved speed: 15/15 Mbps
```

This can be v2.46 if too large for v2.45.

---

# 26. Smart topology policies

Network Layout / topology save should respect:

```text
block_missing_parent_nodes
block_duplicate_node_names
warn_on_virtual_node_promotion
warn_on_deep_hierarchy_depth
max_recommended_depth
```

Before saving topology:

```text
Topology Impact Preview

network.json will change
6 nodes affected
17 clients affected
LibreQoS apply required after save
Risk: Low
```

If invalid:

```text
Topology save blocked.

Reasons:
3 clients reference missing parent nodes.
Duplicate node name found.
```

---

# 27. Backup guard

Recommended policy:

```json
{
  "backup_guard": {
    "require_backup_before_apply": true,
    "warn_if_backup_disabled_while_auto_apply_enabled": true,
    "minimum_backup_retention": 30
  }
}
```

Dashboard card:

```text
Backup Readiness

backup_before_apply: enabled
last backup: 3 minutes ago
retention: 30 backups
restorable: yes
```

If disabled:

```text
Warning:
Auto-apply is enabled but backup_before_apply is disabled.
Recommended: enable backups.
```

---

# 28. Event/audit logging

Every policy decision should be logged in audit events.

Audit event types:

```text
policy_decision
cleanup_blocked
cleanup_confirm_required
cleanup_confirmed
cleanup_applied
apply_blocked
risk_score_changed
recommendation_created
```

Audit event should include:

```json
{
  "event": "cleanup_confirm_required",
  "source": "pppoe",
  "router": "RB5k9-Distro",
  "reason": "source_disabled",
  "affected_rows": 35,
  "policy": "require_confirm_next_run",
  "risk_level": "high",
  "recommendations": []
}
```

---

# 29. State files

This can use existing runtime_state.json or add a dedicated policy state file.

Possible state structure:

```json
{
  "last_policy_decision": {},
  "pending_confirmations": [],
  "cleanup_queue": [],
  "last_successful_source_counts": {
    "pppoe": 35,
    "dhcp": 42,
    "hotspot": 8
  },
  "last_successful_node_counts": {
    "DHCP-LAN-RB5k9-Distro": 12
  }
}
```

If possible, store this under:

```text
/opt/LQoSync/state/policy_state.json
```

or inside existing runtime state if project already centralizes state.

---

# 30. Suggested implementation phases

## v2.45 Smart Policy Center

Implement foundation:

```text
policy config defaults
Policy Center UI
per-source cleanup policy
immediate vs next-run cleanup
require confirmation
mass-removal guard
small-node guard
source-disabled handling
collector-failed preserve behavior
Dry Run verdict
Dashboard policy decision card
audit events
docs
```

## v2.46 Smart Insights

```text
risk score cards
data quality score
backup readiness
speed fallback review
recommendations panel
anomaly detection basics
```

## v2.47 Smart Lifecycle

```text
stale client lifecycle
pending cleanup queue
cleanup history table
confirmation expiry
per-client event timeline
```

## v2.48 Smart Setup / Repair

```text
setup wizard
guided repair assistant
update repair wizard
config health check
```

---

# 31. Acceptance criteria for v2.45

A v2.45 implementation is acceptable when:

```text
1. policies config exists with safe defaults
2. Policy Center UI exposes cleanup/apply policies
3. operator can set PPP/DHCP/Hotspot cleanup behavior independently
4. operator can choose immediate or next-run cleanup
5. source-disabled cleanup can require confirmation
6. collector failure preserves rows by default
7. zero result blocks or warns by policy
8. small-node percentage issue is handled
9. mass-removal guard works with min count and min node size
10. Dry Run shows verdict and policy decision
11. Dashboard shows policy decision card
12. pending confirmations are stored and expire
13. confirmation applies immediate or next run depending on policy
14. audit events record decisions and confirmations
15. no dangerous cleanup happens before policy evaluation
```

---

# 32. Example scenario tests

## Test A: DHCP small node

Before:

```text
DHCP-LAN = 3 clients
Removed = 1
Threshold = 30%
```

Expected:

```text
Not blocked by percentage guard because min_node_size/min_removed_count not met.
Uses small_node_guard.partial_removal_action.
```

## Test B: PPP disabled

Before:

```text
PPP rows = 35
pppoe.enabled = false
```

Policy:

```text
source_disabled_action = require_confirm_next_run
```

Expected:

```text
Dry run verdict: Requires confirmation
No deletion yet
Dashboard shows Confirm PPP cleanup
After confirmation, next run removes PPP rows
```

## Test C: DHCP collector failed

```text
dhcp.enabled = true
API read failed
```

Expected:

```text
DHCP rows preserved
cleanup blocked for DHCP
warning shown
apply blocked if proposed output unsafe
```

## Test D: DHCP zero result

```text
dhcp.enabled = true
scan succeeded
valid leases = 0
previous successful DHCP count = 42
```

Expected:

```text
cleanup blocked or require confirmation depending on zero_result_action
```

## Test E: DHCP immediate cleanup

Policy:

```text
dhcp.normal_inactive_action = cleanup_immediate
dhcp.respect_percentage_guards = false
```

Expected:

```text
Absent DHCP rows removed same cycle
LibreQoS apply runs if files changed and apply guard allows
```

## Test F: Duplicate IP

Policy:

```text
block_apply_on_duplicate_ip = true
```

Expected:

```text
Policy decision blocks apply
Dry Run verdict: Blocked by policy
```

---

# 33. UI wording examples

## Policy blocked

```text
Apply blocked by policy.

Reason:
DHCP source returned zero rows after previous successful scan.

Why this matters:
This may indicate a MikroTik API, VLAN, DHCP server, or collector issue.
Deleting all DHCP rows could remove valid clients from LibreQoS.

Recommended action:
Check DHCP source and run Dry Run again.
```

## Confirmation required

```text
Cleanup confirmation required.

Source:
PPPoE

Reason:
PPPoE collector was disabled in config.

Affected rows:
35

Policy:
Require confirmation, cleanup on next run.

Next action:
Confirm cleanup or re-enable PPPoE collector.
```

## Immediate cleanup allowed

```text
Cleanup allowed.

Source:
DHCP

Reason:
Normal inactive clients.

Policy:
Cleanup immediately.

Result:
Rows will be removed in this sync cycle and LibreQoS will apply if files changed.
```

---

# 34. Final architecture statement

The correct final architecture:

```text
LQoSync should be policy-driven.

Config defines what the operator wants.
Policies define how safely it happens.
Policy engine decides before write/apply.
Dashboard and Dry Run explain every decision.
```

This turns LQoSync into a smart and intelligent production operator tool, not just a sync script.

````

I recommend i-paste mo ito sa original branch, then sabihin mo:

```text
Use this as the implementation spec for v2.45 Smart Policy Center. Do not apply the old patch blindly. Implement directly against the latest full project tree.
````


```markdown
# Suggested Release Roadmap

## v2.45 Smart Policy Center

Main brain of the system.

- policy config defaults
- Policy Center UI
- cleanup policy engine
- per-source policy overrides
- immediate vs next-run cleanup
- confirmation requirement
- mass-removal guard
- source-disabled handling
- collector-failed preserve behavior
- Dry Run verdict
- Dashboard policy decision card
- audit events
- documentation update

## v2.46 Smart Insights

- risk score
- data quality score
- backup readiness
- speed fallback review
- recommendation cards
- anomaly detection basics
- smart warning explanations
- Why / Fix / Next Action messages
- update status recommendation
- fallback-speed review table

## v2.47 Smart Lifecycle

- stale client lifecycle
- pending cleanup queue
- cleanup history
- confirmation expiry
- per-client event timeline
- cleanup applied / blocked / confirmed audit trail
- returned-client detection
- source lifecycle state tracking

## v2.48 Smart Setup / Repair

- setup wizard
- guided repair assistant
- update repair wizard
- config health check
- MikroTik connection test wizard
- LibreQoS path / permission checker
- Git install/adoption checker
- policy preset setup during first install
```

Final instruction to paste sa original branch:

```text
Use the full handoff documentation plus this release roadmap as the implementation spec. Do not apply any old patch blindly. Implement directly against the latest full LQoSync project tree.
```


## v2.49 Policy Settings Integration FULL

LQoSync v2.49 makes Smart Policy Center a real operator settings surface. Policies are no longer hidden or only visible as raw JSON. Operators can edit policy behavior in the WebUI, save it to `config.json -> policies`, compare the current policy against Conservative/Balanced/Aggressive presets, and run Dry Run to preview the effect before scheduler/auto-apply.

### Key behavior

- Policy Center settings are saved to `config.json -> policies`.
- Manual edits switch `policies.mode` to `custom`.
- Preset buttons apply Conservative, Balanced, or Aggressive defaults.
- Config Center includes a Policy Center module for core policy settings and links to the full Policy Center.
- `engine/policy_schema.py` is the schema source for labels, descriptions, choices, defaults, risk labels, preset comparison, and form parsing.
- Setup & Repair focuses on diagnostics/repair actions and links to Documentation rather than duplicating the full manual.

### Source of truth

```text
config.json -> policies        operator intent
engine/policy_schema.py        policy setting metadata
engine/policy_defaults.py      default/preset values
engine/policy_engine.py        runtime decision maker
policy_state.json              pending confirmations and cleanup queue
docs/content/*.md              documentation source blocks
```


## v2.50 Policy-Aware Cleanup Intelligence

LQoSync v2.50 adds optional source-aware stale lifecycle behavior, risk-aware LibreQoS auto-apply, and policy decision trace entries. Grace is disabled by default per source and should only be enabled for stable identities. DHCP environments with randomized MAC addresses should usually keep grace disabled to avoid temporary ghost rows. Risk-aware auto-apply allows low-risk changes to apply automatically while holding medium/high/critical risk changes pending for operator review by default.


## v2.51 Config Schema + Policy Simulation Engine

LQoSync v2.51 adds a Config Center simulation layer. Operators can preview unsaved settings before saving `config.json`. The simulator validates schema health, detects important changes, explains policy impact, computes risk level, and recommends the next action.

New files:

```text
engine/config_schema.py
engine/config_diff.py
engine/config_simulator.py
engine/policy_simulator.py
docs/content/config_schema_policy_simulation.md
```

Config Center now includes a Config Health / Simulation card with a Preview Impact button. This is read-only and does not write config.json or generated LibreQoS files.


## v2.52 Smart Reports + Operator Audit

LQoSync v2.52 adds a Smart Reports center at `/reports`. It summarizes the last 24 hours of sync, dry-run, policy blocked, cleanup confirmation, LibreQoS apply, config change, and audit activity. The page also displays the latest policy decision report, cleanup report, client change report, smart recommendations, and config/operator audit trail. Reports can be exported as JSON, CSV, or Markdown and can be printed from the browser. The reporting engine is read-only and does not change config, generated files, policy state, or LibreQoS.


## v2.53 Client Lifecycle Timeline

LQoSync v2.53 expands the Lifecycle Center into a client timeline and cleanup-state investigation tool. It adds status/source/search filters, selected-client focus, source lifecycle summaries, cleanup queue visibility, pending confirmations, cleanup and confirmation history, recommendations, and JSON/CSV/Markdown exports. Privacy Mode redacts visible client names, parent nodes, IPs, and MACs in lifecycle tables and timelines.


## v2.54.2 Policy Center Setup Guidelines

Policy Center now includes atomic setup guidance for every visible setting. Each field explains what it controls, recommended setup, risk note, config path, recommended value, and risk level. The detailed guide is available at `docs/content/policy_center_settings_guidelines.md`.

This update also normalizes stale lifecycle PPPoE policy naming to the canonical `pppoe` key while accepting the older `ppoe` alias from previous schema builds, preventing false missing-policy warnings after upgrades or fresh installs.


## v2.56 Policy UX + Conflict Intelligence

LQoSync v2.56 adds read-only Policy Conflict Resolver checks, improved current-vs-preset comparison, and Client Identity Handling guidance inside Smart Policy Center.

The conflict resolver explains risky combinations such as immediate cleanup combined with permissive zero-result handling, collector-failed cleanup that could delete rows, source-disabled immediate cleanup, high/critical risk auto-apply, disabled apply guards, and grace enabled for mixed/unstable identity sources.

Client Identity Handling explains that PPPoE usernames are usually stable, DHCP server+MAC is mixed because of private/random MAC behavior, Hotspot is stable only when username/voucher based, and Static/manual rows are operator-controlled.
