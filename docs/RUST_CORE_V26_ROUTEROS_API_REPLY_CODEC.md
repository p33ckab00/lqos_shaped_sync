# Rust Core v2.6 RouterOS API Reply Codec / Offline Parser

Rust Core v2.6 adds `decode-routeros-api-reply`, an offline RouterOS API reply parser.

## Purpose

This phase decodes already-captured RouterOS API words into sanitized rows/traps before any live Rust socket transport is introduced. It is the counterpart to v2.5 `build-routeros-api-sentence`.

## Safety

- No MikroTik socket is opened.
- No credentials are consumed.
- No RouterOS writes are possible.
- Python collectors remain authoritative.
- Sensitive reply fields such as password, token, secret, and key are redacted from decoded output.

## Operation

```json
{
  "version": "1",
  "op": "decode-routeros-api-reply",
  "payload": {
    "words": ["!re", "=name=selftest", "=address=10.0.0.2", "!done"]
  }
}
```

Expected status: `decoded`.

## Web/API

```text
GET  /api/rust-core/routeros-api-reply
POST /api/rust-core/routeros-api-reply
```

## Backend status

This is still not full Rust backend. It is an offline parser/codec step toward a future read-only Rust RouterOS transport adapter.
