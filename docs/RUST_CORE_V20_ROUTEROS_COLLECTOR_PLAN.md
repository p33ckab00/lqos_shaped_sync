# Rust Core v2.0 RouterOS Collector Plan

Rust Core v2.0 adds the `build-routeros-collector-plan` operation.

This is not a full Rust backend yet. It is the next bridge toward that goal: Rust can now derive the exact RouterOS read plan that a future Rust collector must execute, while Python still performs live RouterOS API reads.

## What it does

Given the current `config.json`, Rust produces a deterministic list of RouterOS API reads for enabled routers and enabled sources.

For PPPoE it plans:

```text
/ppp/active
/ppp/secret
/ppp/profile
```

For DHCP it plans:

```text
/ip/dhcp-server/lease
/ip/dhcp-server
```

For Hotspot it plans:

```text
/ip/hotspot/active
/ip/hotspot/user
/ip/hotspot/user/profile
```

Each command includes:

```json
{
  "router": "RB5009",
  "source": "pppoe",
  "path": "/ppp/active",
  "fields": ["name", "address", "caller-id", "comment"],
  "required": true,
  "purpose": "Read active PPPoE sessions.",
  "transport": "routeros-api",
  "mode": "plan_only",
  "trust_role": "active_presence"
}
```

## Safety behavior

This operation is read-only and plan-only.

It does not:

- connect to MikroTik;
- use router credentials;
- mutate config;
- write LibreQoS files;
- run LibreQoS;
- replace Python collectors.

## API

```text
GET /api/rust-core/routeros-collector-plan
GET /api/rust-core/routeros-collector-plan?router=RB5k9-Distro
GET /api/rust-core/routeros-collector-plan?source=pppoe
POST /api/rust-core/routeros-collector-plan
```

POST may provide a custom payload for testing.

## Why this phase matters

A full Rust backend should not start by opening live RouterOS connections. First, Rust must prove it understands the intended collection contract:

1. which resources to read;
2. which fields to request;
3. which reads are required for cleanup safety;
4. which reads are optional metadata;
5. how each read maps into collector trust and source health.

v2.0 freezes that contract.

## Current backend model

```text
Python Flask WebUI             authoritative
Python run_cycle                authoritative
Python RouterOS collectors       authoritative
Rust RouterOS collector plan     shadow/read-only
Rust safety core                 validator/planner/optional authority gates
```

## Next likely phase

The next safe step is a Rust RouterOS transport shadow client. That phase should still avoid replacing Python collectors immediately. It should first compare live Rust reads against live Python reads before Rust becomes authoritative.
