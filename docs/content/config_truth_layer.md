# Config Truth Layer + Live Save Audit

v2.70.11-rc1 keeps Config Center live-save behavior while making every runtime config write pass through one canonical pipeline.

## What changed

- All WebUI/runtime config writes now use one config-write service instead of mixing direct `save_config()` calls with route-specific behavior.
- Live Config Center writes carry a config revision. If another tab or actor changes `config.json` first, stale writes are rejected instead of silently overwriting newer values.
- Every real config write records masked field-level audit diffs: changed path, previous value, new value, effectivity, and explanation.
- Config Change Preview now shows when important changes become effective.
- Policy field cards now show that saved policy edits become effective on the next sync cycle.
- Existing routes remain compatible; `config.json` remains the source of truth and scheduler/run cycles still reread the saved file at their normal boundaries.

## Operator meaning

```text
change in Config Center
        ↓
canonical write pipeline
        ↓
normalize → validate → reconcile preset/custom → diff → audit → save config.json
```

This makes live editing safer without turning the project into a database-backed system. Operators can still work on-the-fly, but the UI now answers three questions more clearly:

1. What changed?
2. When does it become effective?
3. Was this page editing the latest config revision?

## Effectivity examples

- `policies.*` → next sync cycle
- `routers` / collector settings → next sync cycle
- `scheduler.*` → next scheduler loop
- `app.auto_apply` → next live cycle
- `notifications.telegram.*` → next notification dispatch
- `network_mode` and its compatibility flags → next sync cycle / generated `network.json`

## Compatibility and safety

- `network_mode`, `flat_network`, and `no_parent` keep their existing network-layout semantics.
- Sensitive fields such as passwords and tokens remain masked in diffs.
- Legacy compatibility routes stay intact.
- In-flight sync cycles keep their starting snapshot; the next cycle reads the newly saved `config.json`.
