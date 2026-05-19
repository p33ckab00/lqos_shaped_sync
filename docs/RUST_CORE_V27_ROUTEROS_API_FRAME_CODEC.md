# Rust Core v2.7 RouterOS API Frame Codec

LQoSync v2.97.0-rc1 / `lqosync-core` v2.7.0 adds an offline RouterOS API binary frame codec.

## Operation

```text
codec-routeros-api-frame
```

## Purpose

Earlier phases added:

- `build-routeros-api-sentence` for offline RouterOS API command words.
- `decode-routeros-api-reply` for offline `!re`, `!trap`, and `!done` reply words.

v2.7 adds the binary framing layer between those word lists and a future live TCP adapter.

## Encode mode

Input:

```json
{
  "version": "1",
  "op": "codec-routeros-api-frame",
  "payload": {
    "direction": "encode",
    "words": ["/ppp/active/print", "=.proplist=name,address"]
  }
}
```

Output includes:

```text
status=frame_encoded
hex=<RouterOS API frame bytes>
zero_terminated=true
connection_attempt_count=0
live_transport_supported=false
```

## Decode mode

Input:

```json
{
  "version": "1",
  "op": "codec-routeros-api-frame",
  "payload": {
    "direction": "decode",
    "hex": "032172650a3d6e616d653d746573740521646f6e6500"
  }
}
```

Output includes decoded words and byte counts.

## Safety

This is still not full Rust backend.

The codec is offline only:

- No RouterOS socket is opened.
- No MikroTik authentication is attempted.
- No credentials are consumed.
- No collector authority is migrated yet.
- Python collectors remain authoritative.

Any attempt to use `execute=true`, `mode=live`, or `adapter=live` is blocked.

## Sensitive material

Attribute words with sensitive keys are removed from encoded frames:

```text
=password=...
=api-key=...
=token=...
=secret=...
```

The result reports only the count and redaction status.

Valid RouterOS resource paths such as `/ppp/secret/print` remain allowed because they are not credential material by themselves.

## API

```text
GET  /api/rust-core/routeros-api-frame
POST /api/rust-core/routeros-api-frame
```

Example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/routeros-api-frame \
  -H 'Content-Type: application/json' \
  -d '{"direction":"encode","words":["/ppp/active/print","=.proplist=name,address"]}'
```

## Expected self-test marker

```text
routeros_api_frame_codec
```

## Next phase

The next safe bridge is a read-only live transport adapter behind strict authority gates. That phase should still start with one router and one source only.
