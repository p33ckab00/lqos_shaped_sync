# Client Lifecycle Timeline

LQoSync v2.53 expands the Smart Lifecycle Center into a client timeline and cleanup-state investigation tool.

## Purpose

The Lifecycle Center helps operators answer:

- Which clients are active, stale, queued for cleanup, removed, or returned?
- Why was a cleanup queued or preserved?
- Which source is responsible: PPPoE, DHCP, Hotspot, Static, or Unknown?
- Which client changed speed, parent node, IP, MAC, or status?
- Are there pending confirmations or cleanup queue entries?

## Client lifecycle states

- `active` — client is present in the latest generated output.
- `stale` — client is missing but preserved by policy.
- `queued_cleanup` — client is scheduled for cleanup by policy on a later run.
- `confirmed_cleanup` — operator confirmed cleanup and it is waiting to be applied.
- `removed` — client has been removed or cleanup was applied.
- `unknown` — state is incomplete or imported from older runtime state.

## Timeline events

Lifecycle events include:

- `client_added`
- `client_updated`
- `client_returned`
- `client_removed`
- `cleanup_queued`
- `cleanup_preserved`
- `cleanup_applied`

Every event can carry source, reason, parent node, IP, MAC, speed, changed fields, and timestamp.

## Exports

The Lifecycle Center provides JSON, CSV, and Markdown exports so operators can attach a lifecycle report to audits, support requests, or troubleshooting notes.

## Privacy mode

Lifecycle tables and timelines use WebUI redaction classes. When Privacy Mode is enabled, visible client names, nodes, IP addresses, and MAC addresses are masked in the browser only. Source files and state files are unchanged.
