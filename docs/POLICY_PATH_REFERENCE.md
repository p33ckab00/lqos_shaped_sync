# Policy / Path Reference

Policy and path coverage is validated by:

```bash
python3 scripts/policy_path_audit.py
```

The audit checks:

- required runtime paths in `config.json.example`
- Smart Policy schema paths
- Smart Policy default coverage
- migrated config completeness
- missing-policy warnings
- schema errors

Important policy groups:

- cleanup policies
- source-disabled policies
- collector-failed policies
- zero-result policies
- mass-removal guards
- small-node guards
- stale lifecycle
- auto-apply policy
- backup guards
- topology/missing-parent guards
- duplicate-IP guards

If any policy/path audit fails, do not publish or update production until fixed.


## v2.70.2-rc1 Config Policy Hierarchy UI

LQoSync v2.70.2-rc1 reorganizes Config Center → Policies into a compact hierarchy tree. Policies remain inside Config Center to avoid redundant modules, but are now grouped by operator intent: Overview, General Core, PPPoE, DHCP, Hotspot, Static, Cleanup Lifecycle, Mass Removal, Apply Guards, Auto Apply, Backup Policy, Topology/Data, Speed Resolution, and Advanced JSON.

This release also separates required and optional behavior: `app.auto_apply` is required when `app.operation_mode=automatic`, while `app.backup_before_apply` is optional by default to support storage-saving deployments. Production Readiness blocks disabled auto-apply in automatic mode but treats disabled auto-backup as allowed operator choice.


## v2.70.3 Policy Preset Wiring Hotfix

Config Center → Policies now includes visible Conservative, Balanced, and Aggressive preset buttons wired to the saved config preset route. `policies.mode` is displayed as managed preset status instead of a misleading normal field, while manual policy edits still set mode to `custom` when saved.
