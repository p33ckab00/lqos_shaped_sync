# Policy Preset Wiring Hotfix

LQoSync v2.70.3-rc1 fixes the Config Center policy preset workflow after the policy UI was moved into a compact hierarchy under Config Center.

## What was wrong

The old standalone Policy Center had preset forms, but `/policy` now redirects into `Config Center → Policies`. The new hierarchy exposed editable policy fields, but did not provide an operator-visible preset apply control inside Config Center.

Also, `policies.mode` appeared like a normal editable field even though changing that value alone does not apply preset values. A real preset apply must replace the Smart Policy block with the selected preset values.

## What changed

- Config Center → Policies now has visible Conservative, Balanced, and Aggressive preset buttons.
- Preset buttons call the existing owner/admin-protected preset route safely with CSRF.
- Applying a preset writes directly to saved `config.json → policies`.
- `policies.mode` is now shown as a managed/read-only status field in the hierarchy.
- Manual policy field edits still mark the preset mode as `custom` when saved.
- The preset route returns directly to `/config?tab=policies`.

## Correct behavior

- Apply preset = saved config policy block changes to the preset.
- Manual edit = policy mode becomes `custom` after saving.
- Advanced Raw JSON still shows the exact saved result.
- Dry Run should be run after preset changes.
