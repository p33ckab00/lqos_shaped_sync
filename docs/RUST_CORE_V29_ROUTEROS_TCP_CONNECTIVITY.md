# Rust Core v2.9 RouterOS TCP Connectivity Pilot

This release adds a gated TCP connectivity pilot for the `lqosync-in-rust` branch.

## Operation

```text
run-routeros-tcp-connectivity-pilot
```

## Purpose

Previous releases built the offline RouterOS API pipeline:

```text
sentence -> binary frame -> fixture reply -> decoded rows
```

v2.9 adds the first explicitly gated live-network boundary:

```text
Router config
↓
TCP connect rehearsal / pilot
↓
no authentication
↓
no RouterOS API words sent
↓
no replies read
```

## Safety model

Default behavior is rehearsal-only.

```text
connection_attempt_count = 0
authentication_attempt_count = 0
api_sentence_write_count = 0
api_reply_read_count = 0
```

The Python fallback never opens sockets. Only the Rust core can perform a TCP connect, and only when explicit gates are enabled.

## Required gates for a real TCP connect

All must be true:

```json
{
  "execute": true,
  "rust_core": {
    "allow_rust_routeros_tcp_connect": true,
    "routeros_tcp_connect_pilot": true,
    "routeros_transport_authority": "tcp_connect_pilot"
  }
}
```

`live_read_pilot` is also accepted as a transport authority for forward compatibility.

## What this still does not do

v2.9 still does **not**:

- authenticate to MikroTik
- send RouterOS API command words
- read RouterOS API replies
- replace Python collectors
- write LibreQoS files
- become a full Rust backend

## API endpoint

```text
GET  /api/rust-core/routeros-tcp-connectivity-pilot
POST /api/rust-core/routeros-tcp-connectivity-pilot
```

Example rehearsal:

```bash
curl "http://YOUR-LQOSYNC/api/rust-core/routeros-tcp-connectivity-pilot?router=RB5k9-Distro"
```

Example explicit TCP pilot:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-tcp-connectivity-pilot \
  -H 'Content-Type: application/json' \
  -d '{
    "router": "RB5k9-Distro",
    "execute": true,
    "config": {
      "rust_core": {
        "allow_rust_routeros_tcp_connect": true,
        "routeros_tcp_connect_pilot": true,
        "routeros_transport_authority": "tcp_connect_pilot"
      }
    }
  }'
```

## Phase status

```text
Phase: RouterOS transport bridge
Full Rust backend: no
Python collectors: still authoritative
Rust transport: TCP reachability pilot only
```
