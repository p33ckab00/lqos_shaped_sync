# Rust Core Protocol

This document defines the stable JSON protocol for Python ↔ Rust communication in the `lqosync-in-rust` branch.

The protocol must be transport-neutral. The same request and response shape must work over:

```text
- subprocess stdin/stdout
- future Unix socket daemon
- future test fixture files
```

## Request envelope

Every request uses this shape:

```json
{
  "version": "1",
  "op": "validate-config",
  "request_id": "optional-id",
  "payload": {}
}
```

Fields:

| Field | Required | Meaning |
|---|---:|---|
| `version` | yes | Protocol version. Start with string `"1"`. |
| `op` | yes | Operation name. |
| `request_id` | no | Caller-provided ID returned unchanged in the response. |
| `payload` | yes | Operation-specific input. |

## Response envelope

Every response uses this shape:

```json
{
  "version": "1",
  "op": "validate-config",
  "request_id": "optional-id",
  "ok": true,
  "result": {},
  "errors": [],
  "warnings": [],
  "meta": {
    "engine": "lqosync-core",
    "duration_ms": 2.41
  }
}
```

Fields:

| Field | Required | Meaning |
|---|---:|---|
| `version` | yes | Protocol version returned by Rust. |
| `op` | yes | Operation name being answered. |
| `request_id` | no | Echo of request ID, if provided. |
| `ok` | yes | True only if operation completed without blocking errors. |
| `result` | yes | Operation-specific result object. |
| `errors` | yes | Structured errors. Empty list if none. |
| `warnings` | yes | Structured warnings. Empty list if none. |
| `meta` | yes | Runtime metadata such as engine name and duration. |

## Error/warning item

Errors and warnings use the same structure:

```json
{
  "code": "invalid_bandwidth",
  "severity": "error",
  "path": "rows[client1].Download Max Mbps",
  "message": "Invalid bandwidth value",
  "value": "abc",
  "hint": "Use a numeric Mbps value."
}
```

Required fields:

```text
code
severity
message
```

Recommended fields:

```text
path
value
hint
safe_for_cleanup
safe_for_write
safe_for_apply
```

Severity values:

```text
info
warning
error
critical
```

## Operation list

### v0.1 operations

```text
parse-bandwidth
validate-config
validate-shaped-devices
validate-network
validate-files
```

### v0.2 operations

```text
validate-collector-output
diff-shaped-devices
diff-network
```

### v0.3 operations

```text
write-atomic
write-state
append-audit
backup-manifest
```

### v0.4 operations

Same operations as previous phases, but available through Unix socket daemon transport.

## Example: parse-bandwidth

Request:

```json
{
  "version": "1",
  "op": "parse-bandwidth",
  "request_id": "test-001",
  "payload": {
    "value": "50M/20M",
    "format": "rate_limit"
  }
}
```

Response:

```json
{
  "version": "1",
  "op": "parse-bandwidth",
  "request_id": "test-001",
  "ok": true,
  "result": {
    "download_mbps": 50.0,
    "upload_mbps": 20.0,
    "source_format": "rate_limit"
  },
  "errors": [],
  "warnings": [],
  "meta": {
    "engine": "lqosync-core",
    "duration_ms": 0.2
  }
}
```

## Example: validate-files

Request:

```json
{
  "version": "1",
  "op": "validate-files",
  "payload": {
    "config_path": "/opt/libreqos/src/config.json",
    "shaped_devices_csv_path": "/opt/libreqos/src/ShapedDevices.csv",
    "network_json_path": "/opt/libreqos/src/network.json"
  }
}
```

Response:

```json
{
  "version": "1",
  "op": "validate-files",
  "ok": false,
  "result": {
    "risk_level": "critical",
    "write_allowed": false,
    "apply_allowed": false,
    "counts": {
      "rows": 120,
      "nodes": 18
    }
  },
  "errors": [
    {
      "code": "duplicate_ip",
      "severity": "critical",
      "path": "ShapedDevices.csv.IPv4",
      "message": "Duplicate IPv4 address found.",
      "value": "192.168.10.25"
    }
  ],
  "warnings": [],
  "meta": {
    "engine": "lqosync-core",
    "duration_ms": 4.9
  }
}
```

## Python wrapper expectations

`engine/rust_core.py` should expose a small API:

```python
call_rust_core(op: str, payload: dict, request_id: str | None = None) -> dict
validate_files(config_path: str) -> dict
validate_collector_output(payload: dict) -> dict
```

Wrapper behavior:

```text
1. Build protocol envelope.
2. Prefer Unix socket when configured and available.
3. Fall back to subprocess CLI.
4. Parse JSON response.
5. If Rust is unavailable, return a structured fallback response and let current Python validators run.
```

## Transport compatibility rule

The transport can change. The protocol cannot change casually.

Do not return one shape for CLI and a different shape for daemon mode. Python should not know or care whether Rust was called by subprocess or socket.

## Versioning rule

When the protocol shape changes incompatibly:

```text
- increment version
- support old version for at least one release
- document migration in release notes
```

## Implemented v0.1/v0.2-compatible operations in this package

The current scaffold implements the stable envelope and these operations:

```text
parse-bandwidth
validate-config
validate-shaped-devices
validate-network
validate-files
validate-collector-output
```

Example subprocess call:

```bash
printf '%s' '{"version":"1","op":"parse-bandwidth","payload":{"parser":"rate_limit","value":"10M/5M"}}' \
  | rust/lqosync-core/target/release/lqosync-core
```

Example `validate-files` request using inline text:

```json
{
  "version": "1",
  "op": "validate-files",
  "payload": {
    "config": {},
    "csv_text": "Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment\n",
    "network_text": "{}"
  }
}
```

Example `validate-files` request using file paths:

```json
{
  "version": "1",
  "op": "validate-files",
  "payload": {
    "config_path": "/opt/libreqos/src/config.json",
    "shaped_devices_csv_path": "/opt/libreqos/src/ShapedDevices.csv",
    "network_json_path": "/opt/libreqos/src/network.json"
  }
}
```

Python wrapper:

```python
from engine.rust_core import call_rust_core, validate_runtime_outputs, rust_core_status
```

Fallback rule:

```text
If the Rust binary is unavailable, engine.rust_core returns ok=true, skipped=true,
available=false so the current Python path can continue safely.
```

## v0.7 Operation

`evaluate-sync-plan` uses the same protocol envelope and returns an end-to-end shadow plan.
