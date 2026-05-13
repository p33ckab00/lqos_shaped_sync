# LQoSync v2.47 Smart Lifecycle

Smart Lifecycle adds stateful, bounded lifecycle tracking on top of Smart Policy Center. It records whether clients are active, stale, queued for cleanup, confirmed for cleanup, removed, or returned before cleanup.

## What it tracks

- Client lifecycle state by Circuit Name
- Per-client event timeline
- Cleanup queue and cleanup history
- Confirmation history
- Source lifecycle snapshots for PPP, DHCP, and Hotspot
- Returned-client detection

## Why it matters

Policy decisions explain if cleanup is allowed, blocked, or confirmation-required. Smart Lifecycle shows what happened after that decision over time.

Example: if a DHCP client disappears and policy queues cleanup for next run, the Lifecycle Center shows it as queued. If the client returns before cleanup, LQoSync records a returned-client event and marks it active again.

## Files

Lifecycle data is stored in the same Smart Policy runtime state file:

```text
/opt/lqosync/state/policy_state.json
```

This is runtime state, not operator config.
