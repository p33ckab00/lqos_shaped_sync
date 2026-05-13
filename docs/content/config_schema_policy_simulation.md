# Config Schema + Policy Simulation Engine

LQoSync v2.51 adds a read-only simulation layer for Config Center. The goal is to let operators preview settings changes before saving `config.json` or running a live sync.

## What it does

- Adds `config_schema_version` to config.json.
- Migrates missing safe defaults without overwriting operator values.
- Validates required paths, network mode, LibreQoS working directory, policy actions, policy data types, and risky policy combinations.
- Calculates a Config Health score.
- Compares saved config with the in-browser proposed config.
- Simulates policy impact before save.
- Shows verdict, risk level, recommendations, and important changed fields.

## New engine modules

```text
engine/config_schema.py
engine/config_diff.py
engine/config_simulator.py
engine/policy_simulator.py
```

## Config Center behavior

The Config Center side panel now includes **Config Health / Simulation**.

Operators can click:

```text
Preview Impact
```

This sends the current unsaved UI config to `/config/simulate` and returns:

```text
verdict
risk_level
schema health
migration notes
changed fields
important changes
policy simulation
recommendations
```

No files are written. `config.json`, `ShapedDevices.csv`, `network.json`, and LibreQoS are untouched.

## Verdict examples

```text
safe_to_save
```

The proposed config has no major schema or risk issues.

```text
dry_run_recommended
```

The proposed config is valid but changes important behavior. Dry Run is recommended before live scheduler/auto-apply.

```text
save_with_caution_and_dry_run
```

The proposed config changes risky behavior such as auto-apply, source enablement, network mode, or immediate cleanup.

```text
cannot_save
```

The proposed config has schema errors and should not be saved.

## Why this matters

Policy Center gives operators freedom. v2.51 adds a safety preview so that flexibility remains understandable and traceable.

Example:

```text
DHCP normal inactive cleanup:
cleanup_next_run → cleanup_immediate
```

Simulation can explain:

```text
Immediate cleanup enabled.
Missing DHCP rows can be removed in the same sync cycle.
Run Dry Run after saving, especially if auto-apply is enabled.
```

## Design rule

```text
Settings changes should be explainable before they are saved.
```
