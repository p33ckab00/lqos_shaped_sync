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
