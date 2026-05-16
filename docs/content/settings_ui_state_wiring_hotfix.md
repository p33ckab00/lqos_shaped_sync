# Settings UI State Wiring Hotfix

LQoSync v2.70.5-rc1 fixes a Config Center visual-state wiring bug where `policies.mode` could show one preset while the highlighted Policy Preset button showed another preset.

## What happened

The Policy Preset backend and save route were already wired, but the Config Center button highlight was hard-coded to Balanced. If the saved policy mode was `aggressive`, the text showed `Current: aggressive` while the Balanced button remained visually active.

## Fix

The preset buttons now use dynamic Alpine helpers:

```text
policyPresetActive(preset)
policyPresetClass(preset)
policyPresetLabel()
```

The active button now follows `cfg.policies.mode` exactly.

## Extra audit coverage

The UI wiring audit now checks Config Center state wiring:

- main Config Center nav tabs have matching sections
- policy tree buttons have matching panels
- preset buttons do not contain hard-coded active state
- preset active state follows `cfg.policies.mode`
- the save form remains bound to the normalized `config_json` hidden field

## Safety

This is a UI/UX wiring hotfix only. It does not change MikroTik collection, cleanup policy execution, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.
