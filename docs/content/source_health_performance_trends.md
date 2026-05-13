# v2.57 Source Health + Performance Trends

LQoSync v2.57 adds a read-only Health Trends center for operational monitoring.

## What it adds

- Source Health cards for PPPoE, DHCP, and Hotspot
- Router API and sync timing trend summaries
- LibreQoS apply health trend summary
- Internal notification candidates for conditions that may later be sent to Telegram
- `/health` WebUI page
- `/api/health/trends` JSON endpoint

## Source Health

Each source card summarizes:

- active rows from the latest run
- stale and queued lifecycle counts when available
- configured cleanup policy
- zero-result policy
- collector-failed policy
- source warnings
- raw collector metrics

## Performance Trends

Performance trends use recent audit timing samples. The goal is not deep analytics; the goal is early warning when RouterOS API latency, full sync time, or LibreQoS apply time becomes much slower than normal.

## LibreQoS Apply Health

The apply health card shows recent successful and failed apply runs, average duration, repeated failures, and pending apply warnings. This helps operators see whether generated files are being applied reliably.

## Notification foundation

v2.57 creates internal notification candidates. These are shown in the WebUI only. Telegram delivery is intentionally planned for v2.58 so secrets, test-message workflow, and notification rules can be implemented safely.

## Safety

The Health Trends center is read-only. It does not modify config.json, generated files, policy state, scheduler behavior, or LibreQoS apply behavior.
