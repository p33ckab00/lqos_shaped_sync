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
