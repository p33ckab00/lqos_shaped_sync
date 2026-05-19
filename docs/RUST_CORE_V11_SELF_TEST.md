# Rust Core v1.1 Runtime Self-Test and Capability Audit

Rust Core v1.1 adds a safe runtime self-test layer for the `lqosync-in-rust` branch.

## Purpose

The v1.0 package introduced `execute-apply-transaction`. Server testing showed the Rust crate built and all unit tests passed, but the binary emitted a warning because the transaction function was imported without being routed by `main.rs`. v1.1 fixes that class of problem by:

- routing `execute-apply-transaction` through the CLI/daemon protocol;
- adding a transport-safe `self-test` operation;
- centralizing the advertised operation list;
- exposing `/api/rust-core/self-test` from the Python WebUI;
- documenting how to verify daemon/binary capability before enabling authority flags.

## New Rust operation

```json
{
  "version": "1",
  "op": "self-test",
  "payload": {
    "strict": false
  }
}
```

The operation is read-only. It does not mutate `ShapedDevices.csv`, `network.json`, state files, audit logs, or LibreQoS.

## What it checks

The self-test verifies:

1. advertised operations are unique;
2. `execute-apply-transaction` is advertised and routed;
3. unit, rate-limit, and comment bandwidth parsers work;
4. a no-change apply manifest can be generated;
5. a transaction rehearsal does not execute writes.

## WebUI/API endpoint

```text
GET /api/rust-core/self-test
GET /api/rust-core/self-test?strict=1
```

The endpoint calls the same transport used by the rest of the wrapper. If `rust_core.prefer_daemon=true` and `/run/lqosync-core.sock` exists, it uses the daemon. Otherwise it falls back to subprocess, then reports unavailable if no Rust core is installed.

## Operator verification commands

```bash
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Daemon socket test:

```bash
python3 - <<'PYTEST'
import json, socket
req = {"version": "1", "op": "self-test", "payload": {}}
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("/run/lqosync-core.sock")
s.sendall(json.dumps(req).encode())
s.shutdown(socket.SHUT_WR)
print(s.recv(65536).decode())
s.close()
PYTEST
```

Expected result:

```json
{
  "ok": true,
  "result": {
    "status": "ok",
    "failed_check_count": 0
  }
}
```

## Optional status integration

By default, `/api/rust-core/status` stays lightweight and does not run the self-test. Operators may enable:

```json
"rust_core": {
  "self_test_on_status": true
}
```

Only enable this when the small extra Rust call is acceptable on status refreshes.

## Safety

v1.1 does not change cleanup, write, or apply authority. Python remains authoritative unless previous opt-in flags such as `enforce_sync_plan`, `execute_apply_manifest`, and `allow_rust_file_writes` are explicitly enabled.
