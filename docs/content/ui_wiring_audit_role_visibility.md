# UI Wiring Audit + Role Visibility Hotfix

LQoSync v2.70.4-rc1 adds a deeper UI wiring audit and fixes several wiring issues that normal route/template tests could not detect.

## What it checks

The UI wiring audit validates:

- literal `user.role == 'admin'` checks are not used in templates after owner/admin/operator/viewer role hardening
- Config Center policy preset buttons are wired to `POST /policy/apply-preset/<preset>`
- compatibility routes point to canonical compact UI locations
- owner-only `/updates` links are role-gated
- known stale files such as `templates/routers.html` and `app.py.pre_reports_route_fix` are not present

## New command

```bash
cd /opt/lqosync
python3 scripts/ui_wiring_audit.py
```

Expected clean result:

```text
Verdict: pass
OK=5 WARN=0 FAIL=0
```

## Role visibility fixes

Owner accounts now see admin-capable action buttons because templates use:

```jinja2
role_at_least(user.role, 'admin')
```

instead of:

```jinja2
user.role == 'admin'
```

This fixes action buttons for Dashboard, Network Layout, Shaped Devices, Operations Center, Backup Preview, and compatibility templates.

## Canonical UI rule

The compact UI ownership remains:

- Policies live inside Config Center → Policies
- Router Insight lives inside Config Center → Routers
- Services/logs/backups live inside Operations Center
- Update Center is owner-only
- Deprecated routes remain compatibility aliases only
