# Stable Release Checklist

Use this checklist before tagging or deploying LQoSync v2.70 stable candidates.

## Preflight

```bash
cd /opt/lqosync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
```

## Operator review

- Dashboard loads without internal errors.
- Config Center loads all tabs.
- Operations Center tabs load: services, journals, apply, logs, audit, backups.
- Reports and Lifecycle load.
- Setup Wizard and System Validation load.
- Update Center clearly shows git relation and update guidance.
- Privacy/masked mode hides sensitive client/router/IP data.
- Owner/admin/operator/viewer role visibility is correct.
- Mobile view has no critical overflow on main pages.

## Release discipline

- No new sidebar modules.
- No duplicate settings pages.
- No missing policy/path warnings.
- No stale route links.
- No undocumented production behavior changes.


## v2.70.1-rc1 Stable RC Stale Template Cleanup Hotfix

This hotfix adds `scripts/cleanup_stale_files.py` for older ZIP/manual installs that may keep files removed from the canonical package. The first known stale file is `templates/routers.html`, because Router Insight now lives in Config Center → Routers and `/routers` redirects there. Run `python3 scripts/cleanup_stale_files.py --apply` then rerun `python3 scripts/stable_release_check.py`.


## v2.70.4-rc1 UI Wiring Audit + Role Visibility Hotfix

LQoSync v2.70.4-rc1 adds `scripts/ui_wiring_audit.py` and fixes role-visibility gaps after owner/admin/operator/viewer hardening. Admin-capable actions now use `role_at_least(user.role, 'admin')`, operator dry-run actions use `role_at_least(user.role, 'operator')`, owner-only Update Center links are gated, Config Center policy preset wiring is audited, and stale files such as `app.py.pre_reports_route_fix` are removed from stable packages.


## v2.70.5 Settings UI State Wiring Hotfix

LQoSync v2.70.5-rc1 fixes the Config Center → Policies preset active-state mismatch. The active Conservative/Balanced/Aggressive button now follows `cfg.policies.mode`, so `Current: aggressive` highlights Aggressive, `Current: balanced` highlights Balanced, and `Current: conservative` highlights Conservative. The UI wiring audit now also checks Config Center nav/section pairing, policy tree/panel pairing, preset active-state binding, and normalized config save binding.


## v2.70.6 Checkbox State Wiring Hotfix

LQoSync v2.70.6 fixes Config Center checkbox visual-state wiring. Boolean policy fields now use normalized checked binding through `asBool(getPath(...))`, explicit `x-effect` checked synchronization, and visible checked-state CSS so true values display with a clear checked mark in light and dark mode. UI wiring audit now checks this behavior.


## v2.70.7 LibreQoS Apply Failure Visibility

LQoSync v2.70.7-rc1 makes failed LibreQoS apply runs actionable. Dashboard and Telegram apply warnings now link to an apply diagnostic page when a run ID is available. Operations Center → Apply History includes a Detail / Resolve button and failed runs show a short summary and resolution hint. The new `/libreqos/apply/<run_id>` page shows stderr/stdout tails, command metadata, failure classification, suggested resolve page, and suggested commands. This is a UI/diagnostics wiring improvement only.


## v2.70.8 Policy Preset Alignment + Save Semantics

LQoSync v2.70.8 aligns Conservative, Balanced, and Aggressive presets so they do not create high/critical conflicts immediately after apply. Aggressive mode still uses faster normal inactive cleanup, but PPPoE/DHCP/Hotspot zero-result cleanup remains `block_cleanup`. Config Center saves now reconcile policy mode server-side: exact presets keep their preset name, while edited policy values are saved as `custom`. The new `scripts/policy_preset_audit.py` validates preset alignment, user preference preservation, and custom-mode reconciliation.


## v2.70.9 Custom Policy Mode Persistence

Config Center → Policies now shows Custom as a visible policy state beside Conservative, Balanced, and Aggressive. Manual policy edits change the UI state to Custom immediately, and server-side save preserves explicit `policies.mode = custom`. Named presets still stay named when exact, and edited named presets reconcile to Custom.


## v2.70.10 Policy Overview Custom Wiring Hotfix

Changing Operation Mode, Auto Apply, Optional Auto Backup, or Backup Retention inside Config Center → Policies now marks `policies.mode` as `custom` and remains custom after save. Server-side save also detects these policy-adjacent `app.*` changes so the mode is protected even if browser JS misses the change event.
