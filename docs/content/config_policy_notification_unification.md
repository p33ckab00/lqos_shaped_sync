# Config + Policy + Notification Unification

v2.62 reduces settings redundancy by making Config Center the single operator-facing home for normal settings, Smart Policy Center settings, and Telegram notification delivery settings.

## What changed

- Policy Center settings are now a native Config Center tab.
- Notification delivery settings are now a native Config Center tab.
- `/policy` remains as a compatibility alias and redirects to `/config?tab=policies`.
- `/notifications` remains as a compatibility alias and redirects to `/config?tab=notifications`.
- Advanced Raw JSON still mirrors the same `config.json` payload.
- Dry Run remains the canonical place to preview runtime impact before enabling scheduler or auto-apply.

## Why

Policies and notifications are configuration. Keeping them as isolated pages made the project feel larger and created multiple places to look for operator intent. The new model is:

```text
Config Center = settings, policies, notification delivery, raw JSON
Dashboard = live health and active alerts
Operations Center = services, logs, journals, backups
Reports = export/report snapshots
Documentation Center = searchable manual
```

## Operator workflow

1. Open Config Center.
2. Edit normal settings, policies, or Telegram delivery settings from tabs.
3. Use Preview Impact to check unsaved config changes.
4. Save normalized config.json.
5. Run Dry Run before production scheduler/auto-apply changes.

## Compatibility

Old links are preserved:

```text
/policy        → /config?tab=policies
/notifications → /config?tab=notifications
```

Existing POST endpoints for policy presets, cleanup confirmations, Telegram test, and Telegram current-alert delivery remain available for compatibility.
