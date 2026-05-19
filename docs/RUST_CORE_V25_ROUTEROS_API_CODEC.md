# Rust Core v2.5 RouterOS API Sentence Codec

LQoSync v2.95.1-rc1 / `lqosync-core` v2.5.1 adds an offline RouterOS API sentence codec.

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


## v2.5.1 redaction hotfix

The codec still accepts RouterOS resource paths such as `/ppp/secret`, but it no longer returns the exact names of sensitive `.proplist` fields that were dropped. Instead, the result exposes:

```json
{
  "dropped_sensitive_field_count": 2,
  "dropped_sensitive_fields_redacted": true
}
```

This avoids leaking field names like `api-key` or `password` in operator-visible payloads while still confirming that sensitive fields were removed.
