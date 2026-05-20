# Policy Preset Alignment + Save Semantics

LQoSync v2.70.8-rc1 aligns Conservative, Balanced, and Aggressive policy presets with the stable safety model while keeping Custom available for operator preference.

## Preset alignment

All built-in presets now follow these baseline safety rules:

- PPPoE, DHCP, and Hotspot collector failure preserves rows.
- PPPoE, DHCP, and Hotspot zero-result cleanup is blocked by default.
- Static/manual rows are preserved.
- Presets replace only `config.json → policies`.
- Presets preserve operator preferences outside the policy block, including `app.backup_before_apply`, Telegram settings, operation mode, and router settings.

Aggressive mode still speeds up normal inactive cleanup, but zero-result is not treated as normal inactivity. A full zero-result from an enabled source can mean API, VLAN, query, profile, or source trouble, so cleanup remains blocked.

## Custom save semantics

Config Center already marks manual policy field edits as `custom` in the browser. v2.70.8 adds server-side reconciliation too:

- If saved policy values exactly match Conservative, mode remains `conservative`.
- If saved policy values exactly match Balanced, mode remains `balanced`.
- If saved policy values exactly match Aggressive, mode remains `aggressive`.
- If saved policy values differ from the selected preset, mode becomes `custom`.

This protects raw JSON edits, old forms, browser edge cases, and future UI changes.

## Audit command

```bash
cd /opt/LQoSync
python3 scripts/policy_preset_audit.py
```

The audit verifies preset mode alignment, zero-result safety, conflict cleanliness, user preference preservation, and custom-mode reconciliation.
