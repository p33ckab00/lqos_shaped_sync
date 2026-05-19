# Rust Core v2.5 RouterOS API Sentence Codec

LQoSync v2.95.0-rc1 / `lqosync-core` v2.5.0 adds an offline RouterOS API sentence codec.

## Operation

```text
build-routeros-api-sentence
```

The operation converts a planned RouterOS read path into deterministic RouterOS API words, including `.proplist` handling and offline word-length metadata. It is a protocol-preparation step before a future read-only socket adapter.

## Safety

This phase does **not** open sockets, does **not** authenticate to MikroTik, and does **not** replace Python collectors. Sensitive fields such as password, token, key, and secret are removed from the generated `.proplist`. The RouterOS resource path `/ppp/secret` remains valid, but secret credential material is not emitted.

## API

```text
GET  /api/rust-core/routeros-api-sentence
POST /api/rust-core/routeros-api-sentence
```

Example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-api-sentence \
  -H 'Content-Type: application/json' \
  -d '{"path":"/ppp/active","fields":["name","address","caller-id"]}'
```

Expected safe result:

```text
status=encoded
connection_attempt_count=0
live_transport_supported=false
```

## Why this matters

Before Rust can safely perform live RouterOS reads, the API command encoding must be deterministic, tested, and redaction-safe. This phase adds that foundation without granting live transport authority.
