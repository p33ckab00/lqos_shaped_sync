# Custom Policy Mode Persistence Hotfix

LQoSync v2.70.9-rc1 fixes the Custom policy mode experience inside Config Center → Policies.

## What changed

- `custom` is now a visible policy state in the preset header.
- Manual policy edits change the UI state to `custom` immediately.
- Server-side Config Center save keeps `policies.mode = custom` when the operator intentionally saves a custom policy block.
- Named presets still work normally: Conservative, Balanced, and Aggressive replace only `config.json → policies`.
- Named preset saves still reconcile to `custom` if their actual values are edited.

## Why this matters

Custom policy mode is an operator preference. It should not disappear just because the current custom values are close to a named preset or because a save path reconciles modes server-side.

## Correct behavior

```text
Click Conservative/Balanced/Aggressive
→ config.json policies are replaced by that preset
→ policies.mode becomes that preset

Edit any visible policy field
→ UI immediately shows Custom
→ save keeps policies.mode = custom

Edit policy values through Advanced Raw JSON
→ save reconciles to custom if values differ from the selected named preset
→ if mode is explicitly custom, save preserves custom
```
