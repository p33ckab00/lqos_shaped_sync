# Smart Reports + Operator Audit

LQoSync v2.52 adds an operator-facing Smart Reports center at `/reports`. The page summarizes the last 24 hours of sync, dry-run, policy, cleanup, configuration, LibreQoS apply, and audit events.

## What it reports

- 24h sync and dry-run summary
- failed sync count
- policy blocked count
- cleanup confirmation count
- latest policy decision and risk level
- cleanup report with removed, queued, preserved, and pending confirmation counts
- client change report from the latest run
- config/operator audit report
- smart recommendations from Smart Insights

## Export options

Reports can be exported as JSON, CSV, or Markdown. The page also has a print-friendly layout for browser print/PDF workflows. Exports are read-only and do not write config, generated files, or LibreQoS state.

## Source of truth

The report uses existing runtime state, policy state, audit events, apply history, services, and backup metadata. It does not create a separate database.
