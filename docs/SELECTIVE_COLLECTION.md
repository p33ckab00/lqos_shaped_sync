# LQoSync Selective MikroTik Collection and Universal Speed Resolver

LQoSync v2.38 adds the next scale-readiness layer for hundreds to thousands of clients. The goal is not to make more MikroTik API calls. The goal is to make fewer, more precise reads and then perform fast local matching in memory.

## Design goals

- Bulk-read RouterOS resources once per source.
- Request only the fields needed for `ShapedDevices.csv` and `network.json`.
- Avoid per-client API calls.
- Build local dictionaries for fast lookup.
- Resolve speeds through one universal speed resolver.
- Record the exact speed source and raw source value for audit, Dashboard, and Shaped Devices detail panels.
- Keep source-aware cleanup so PPP/DHCP/Hotspot rows are only cleaned when that source scan succeeded.
- Keep LQoSync database-free by using JSON state/cache files only.

## PPPoE read process

LQoSync reads:

```text
/ppp/active
/ppp/secret
/ppp/profile
```

Selected fields:

```text
/ppp/active:  name, address, caller-id, comment
/ppp/secret:  name, profile, comment, caller-id, disabled, inactive
/ppp/profile: name, comment, rate-limit
```

Processing:

```text
/ppp/active decides who is online
active.name -> /ppp/secret by name
secret.profile -> /ppp/profile by name
resolve speed
create/update ShapedDevices.csv row
```

Speed priority:

```text
1. PPP secret comment
2. PPP active comment
3. PPP profile comment
4. PPP profile name
5. PPP profile rate-limit
6. config default_pppoe_rate
```

## DHCP read process

LQoSync reads:

```text
/ip/dhcp-server/lease
/ip/dhcp-server
```

Selected fields:

```text
/ip/dhcp-server/lease: server, mac-address, active-address, address, host-name, comment, status, disabled, dynamic
/ip/dhcp-server:       name, comment
```

Dynamic lease comments are not treated as the first speed source because RouterOS lease comments are not reliable for dynamic clients unless the lease is static. Instead, speed is server-based.

Speed priority:

```text
1. DHCP server speed text / config speed_comment / MikroTik DHCP server comment
2. DHCP server name
3. DHCP server config speed
4. global default DHCP speed
```

DHCP lease modes:

```text
permissive: server matches + MAC exists + active-address/address exists
strict:     server matches + MAC exists + status=bound + active-address exists
```

`permissive` is the default because it matches existing production behavior.

## Hotspot read process

LQoSync reads:

```text
/ip/hotspot/active
```

If enhanced metadata is enabled, it also reads:

```text
/ip/hotspot/user
/ip/hotspot/user/profile
```

Selected fields:

```text
/ip/hotspot/active:       user, address, mac-address, server, comment
/ip/hotspot/user:         name, profile, comment
/ip/hotspot/user/profile: name, comment, rate-limit
```

Speed priority:

```text
1. Hotspot user comment
2. Hotspot profile comment
3. Hotspot profile name
4. Hotspot profile rate-limit
5. Hotspot config speed
6. global default Hotspot speed
```

## Metadata cache

The metadata cache is stored at:

```text
/opt/lqosync/state/collector_cache.json
```

It records source hashes and cache metrics. It is not a database. It is used for observability and future optimization phases.

Dashboard shows:

```text
cache hits
cache misses
source hash changes
collector read durations
speed-source counts
```

## Source-aware cleanup

Cleanup is source-aware:

```text
PPP rows are cleaned only if PPP scan succeeded.
DHCP rows are cleaned only if DHCP scan succeeded.
Hotspot rows are cleaned only if Hotspot scan succeeded.
```

This prevents accidental mass removal when one RouterOS API source fails.

## Dashboard monitoring

v2.38 adds Dashboard cards for:

```text
Collector Health
Source Counts
Speed Source Breakdown
Cache Efficiency
LibreQoS Apply State
Detailed Last Sync Timeline
```

These cards help identify whether slowness is coming from MikroTik API reads, local parsing, file rendering, cache changes, or LibreQoS apply.

## Not included yet

The following are intentionally left for a later phase:

```text
separate PPP/DHCP/Hotspot scan intervals
multi-router concurrency
server-side table pagination
```

v2.38 focuses on correctness, safety, and visibility before adding more scheduling/concurrency complexity.
