# Telegram Runtime Feed — Safety Alerts + Activity Journal

v2.71 adds the missing bridge between engine events and Telegram delivery.

Before v2.71, **Test Telegram** could succeed while normal runtime work produced no Telegram update because only manual health-alert sending used the delivery helper. Now real sync and manual force-apply flows generate runtime candidates directly.

## Why two lanes

```text
Safety Alerts
  policy blocked
  confirmation required
  LibreQoS apply failed

Activity Journal
  client records changed
  generated files changed
  LibreQoS apply succeeded
```

The lanes have separate dedupe state. Safety alerts stay warning/critical-oriented and audible. Activity journal entries are informational, digest-first, and silent by default so operators gain visibility without turning Telegram into noise.

## How to verify it is wired

1. Enable Telegram in Config Center → Notifications.
2. Keep both lanes enabled.
3. Run a real sync that adds/updates/removes a client, or complete a successful LibreQoS apply.
4. Check Audit Logs for `telegram_runtime_activity`.
5. Trigger a policy block or failed apply in a safe test environment and check for `telegram_runtime_alerts`.

## Operational interpretation

- `telegram_test_sent` means credentials/transport worked.
- `telegram_current_alerts_sent` means the manual current-health sender ran.
- `telegram_runtime_activity` means the live engine emitted operator-journal events.
- `telegram_runtime_alerts` means the live engine emitted urgent runtime alerts.

That distinction is important: transport success and runtime wiring are different truths.
