# Router Insight De-duplication + Policy/Path Audit

LQoSync v2.69.1 removes Router Overview as a separate top-level UI module because router insight belongs beside router configuration.

## What changed

- The sidebar no longer shows a standalone Routers page.
- `/routers` remains as a compatibility alias, but redirects to `Config Center → Routers`.
- Router insight is shown inside the Config Center Routers tab as a read-only operational summary.
- `templates/routers.html` is removed from the active package because it duplicated Config Center router settings.
- `/api/routers/overview` remains available for read-only diagnostics.
- A new policy/path audit verifies required runtime paths, policy schema paths, policy defaults, migrated config, and missing-policy warnings.

## Why

Router settings and router insight should not be split into two pages. The operator should see the saved router config and the read-only generated-row/source hints in one place.

## Operator workflow

1. Open Config Center.
2. Open Routers.
3. Review Router Insight summary.
4. Edit router/source settings below the insight summary.
5. Run Dry Run after changing router settings.

## Policy/path audit

Run:

```bash
cd /opt/LQoSync
python3 scripts/policy_path_audit.py
```

It checks:

- required runtime paths
- policy schema paths in migrated config
- policy defaults coverage
- missing-policy warnings
- schema errors

It is also included in `release_check.py`, `regression_check.py`, and `lqosync-doctor.sh`.
