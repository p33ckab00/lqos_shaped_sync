# Rust Core v0.4 Daemon Mode

This update adds an optional long-running `lqosync-core` Unix socket daemon. The daemon uses the exact same JSON request/response envelope as the CLI, so Python does not need separate operation schemas for subprocess and daemon transport.

## Why daemon mode exists

Subprocess calls are safe and easy to debug, but spawning a binary repeatedly can add overhead when validation, autosave, dry-run, and sync cycles become more Rust-backed. Daemon mode keeps the Rust core warm and accepts requests over a local Unix socket.

## Default behavior

Daemon mode is optional. The default remains safe:

```text
rust_core.prefer_daemon = false
```

When `prefer_daemon=false`, Python continues to call the Rust core through subprocess if the binary is available. When `prefer_daemon=true`, Python tries the Unix socket first and falls back to subprocess if the socket transport fails. If neither is available, Python fallback remains active.

## Service installation

Build and install the Rust binary first:

```bash
cd /opt/LQoSync
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
```

Then install the daemon service:

```bash
sudo scripts/install-rust-core-daemon.sh
```

Check status:

```bash
systemctl status lqosync-core --no-pager
ls -l /run/lqosync-core.sock
```

## Enable Python daemon preference

In `config.json`:

```json
"rust_core": {
  "enabled": true,
  "prefer_daemon": true,
  "unix_socket": "/run/lqosync-core.sock"
}
```

Restart LQoSync after changing this setting.

## Manual daemon test

```bash
printf '{"version":"1","op":"health","payload":{}}' | lqosync-core
```

Daemon transport test using Python:

```bash
python3 - <<'PY'
import json, socket
req = {"version":"1","op":"health","payload":{}}
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/run/lqosync-core.sock')
s.sendall(json.dumps(req).encode())
s.shutdown(socket.SHUT_WR)
print(s.recv(65536).decode())
s.close()
PY
```

## Rollback

Disable daemon mode in config or uninstall the service:

```bash
sudo scripts/uninstall-rust-core-daemon.sh
```

Python will continue to use subprocess or fallback mode.
