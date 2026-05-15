# Config Policy Hierarchy UI

LQoSync v2.70.2-rc1 makes the configurable Smart Policies easier to understand by keeping them inside Config Center and arranging them as a compact hierarchy.

## Location

```text
Config Center → Policies
```

The Policy UI is not a separate module. It is part of Config Center so router/source settings, apply behavior, backup policy, and raw JSON remain in one operator control plane.

## Hierarchy

The Policies tab is grouped by operator intent:

- Overview
- General Core
- PPPoE
- DHCP
- Hotspot
- Static/manual rows
- Cleanup Lifecycle
- Mass Removal Guards
- Apply Guards
- Auto Apply
- Backup Policy
- Topology/Data Quality
- Speed Resolution
- Advanced JSON

Every visible policy field shows:

- human-readable label
- current value
- recommended value
- risk badge
- description
- config path
- setup/risk guidance when available

## Required, recommended, and optional settings

LQoSync separates settings into three classes:

### Required

Required settings are needed for automatic production operation:

- valid config
- valid generated-file paths
- at least one enabled MikroTik router
- at least one enabled PPPoE/DHCP/Hotspot source
- complete policy paths/defaults
- no schema errors
- `app.auto_apply=true` when `app.operation_mode=automatic`

### Recommended

Recommended settings improve safety but are not always mandatory:

- Dry Run before scheduler
- release/regression/policy-path checks before update
- manual backup before major update
- Telegram notifications
- resolving config warnings

### Optional

Optional settings depend on operator preference and deployment style:

- `app.backup_before_apply`
- grace/anti-flap
- Telegram delivery
- long lifecycle/report history
- theme/privacy preferences

## Auto Apply vs Auto Backup

LQoSync now treats these separately:

```text
Auto Apply = required in automatic mode
Auto Backup = optional storage/rollback policy
```

This means:

- `app.operation_mode=automatic` and `app.auto_apply=false` is a production readiness blocker.
- `app.backup_before_apply=false` is allowed storage-saving mode.
- Disabled auto-backup reduces automatic rollback convenience but should not block production readiness by default.

Operators that want auto-backup to be mandatory can enable:

```text
policies.backup_guard.require_backup_before_apply=true
```

## Speed Resolution visibility

The Policy Hierarchy includes the speed-resolution priority ladders for PPPoE, DHCP, and Hotspot so operators can see why a subscriber receives a plan speed or fallback speed.

## Advanced JSON

Advanced Raw JSON remains available as a fallback and audit surface, but the hierarchy is the primary operator UI.
