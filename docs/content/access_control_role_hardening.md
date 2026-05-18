# Access Control + Role Hardening

LQoSync v2.67 adds a clearer role hierarchy so production operators can separate ownership, administration, operations, and read-only access.

## Roles

| Role | Purpose |
| --- | --- |
| `owner` | Full control, including user management, Update Center, setup/repair high-trust controls, config, policies, backups, and live actions. |
| `admin` | Can manage config, policies, scheduler, operations, backups, and LibreQoS apply actions, but cannot manage users or owner-only update controls. |
| `operator` | Can monitor, inspect operations, review reports/lifecycle, and run dry-run style previews. Cannot change production config/policies or perform destructive actions. |
| `viewer` | Read-only dashboards, shaped devices, reports, documentation, and status pages. |

## Upgrade behavior

Older installs may only have `admin` and `viewer`. During user-store normalization, if no `owner` exists, the first existing `admin` is promoted to `owner`. This prevents lockout after upgrading to owner-only user/update controls.

## Protected actions

Owner-only actions include:

- Users & Roles management
- Update Center
- Smart Defaults Repair
- Release integrity API

Admin-or-owner actions include:

- Config Center writes
- Policy and notification settings
- Scheduler enable/disable/run-now
- Service restart/group restart
- Backup restore/delete
- LibreQoS force apply
- Setup Wizard and Setup & Repair operations

Operator-or-above actions include:

- Running Dry Run previews

Viewer actions remain read-only.

## Safety rules

LQoSync prevents deleting the current logged-in user, deleting the last owner, demoting the last owner, and removing the last admin-capable account. Passwords continue to be stored as bcrypt hashes in `users.json`.

## Recommended setup

For production, use at least two owner/admin-capable accounts:

1. One `owner` account for system ownership and updates.
2. One `admin` account for daily configuration and operations.
3. Optional `operator` accounts for staff who need visibility and dry-run previews.
4. Optional `viewer` accounts for read-only support access.
