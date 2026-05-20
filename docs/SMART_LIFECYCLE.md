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
/opt/LQoSync/state/policy_state.json
```

This is runtime state, not operator config.


## v2.53 Client Lifecycle Timeline

LQoSync v2.53 expands the Lifecycle Center into a client timeline and cleanup-state investigation tool. It adds status/source/search filters, selected-client focus, source lifecycle summaries, cleanup queue visibility, pending confirmations, cleanup and confirmation history, recommendations, and JSON/CSV/Markdown exports. Privacy Mode redacts visible client names, parent nodes, IPs, and MACs in lifecycle tables and timelines.
