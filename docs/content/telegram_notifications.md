# v2.71 Telegram Notifications

LQoSync v2.71 turns Telegram from a manual delivery test into a real runtime feed. Telegram remains optional, but when enabled it now has two independent lanes:

```text
Safety Alerts     = urgent runtime events that should be hard to miss
Activity Journal  = quiet, digest-first operator history of meaningful work
```

Internal Dashboard notifications still work even when Telegram is disabled.

## What Telegram can send

### Safety Alerts

- LibreQoS apply failures
- policy blocks / high-risk holds
- cleanup confirmation-required events
- source-health warnings
- performance slowdowns
- update-available events when exposed as candidates

### Activity Journal

- client records added / updated / removed during a real sync cycle
- successful LibreQoS applies
- generated-file changes when output changed without client-row movement

The activity lane intentionally does **not** depend on `notify_levels`; its messages are informational by design. By default they are digest-first and silent in Telegram so they behave like a journal, not like an alarm bell.

## Configuration location

Open:

```text
Config Center → Notifications
```

Settings are saved under:

```text
config.json → notifications.telegram
```

Important fields:

```json
{
  "notifications": {
    "telegram": {
      "enabled": false,
      "safety_alerts_enabled": true,
      "activity_journal_enabled": true,
      "activity_send_digest": true,
      "activity_send_individual": false,
      "activity_silent_messages": true,
      "notify_levels": ["critical", "warning"],
      "minimum_interval_seconds": 60,
      "dedupe_window_minutes": 60,
      "send_digest": true,
      "send_individual": false,
      "notify_on_client_changes": true,
      "notify_on_apply_success": true,
      "notify_on_files_written": true
    }
  }
}
```

## Runtime wiring

A successful test message only proves credentials and transport. v2.71 also wires real runtime events:

```text
sync cycle / force apply
        ↓
runtime event candidates
        ↓
Safety Alerts lane OR Activity Journal lane
        ↓
Telegram dispatch + lane-specific dedupe state
```

That means client changes and apply results are emitted by the engine itself, not only by the manual **Send current alerts** button.

## Recommended setup

1. Create a Telegram bot using BotFather.
2. Save the bot token and target chat ID.
3. Keep **Safety Alerts** enabled with warning + critical levels.
4. Keep **Activity Journal** enabled in digest mode; leave silent messages on unless you truly want audible journal traffic.
5. Click **Test saved Telegram** to verify credentials.
6. Let one real sync cycle run, then verify audit entries such as `telegram_runtime_activity` or `telegram_runtime_alerts` when relevant events occur.

## Dedupe and rate limiting

Telegram delivery includes two safety controls:

```text
minimum_interval_seconds
```

Prevents repeat sends too quickly.

```text
dedupe_window_minutes
```

Suppresses repeated identical events for a configured time window. v2.71 stores state separately per lane so a quiet activity digest does not suppress an urgent safety alert.

## Security notes

Telegram bot tokens are secrets. They are masked in UI summaries, but stored in `config.json`. Protect file permissions and avoid sharing raw config screenshots.
