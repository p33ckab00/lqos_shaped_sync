import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _running_in_container() -> bool:
    return Path("/.dockerenv").exists() or bool(os.getenv("container"))


def _is_baremetal_mode() -> bool:
    install_mode = (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower()
    if install_mode in {"baremetal", "host", "systemd"}:
        return True
    if _truthy(os.getenv("LQOSYNC_FORCE_DIRECT"), False):
        return True
    # Safety fallback: host_nsenter only makes sense from inside the Docker host-integrated container.
    if install_mode not in {"docker", "container"} and not _running_in_container():
        return True
    return False


def _apply_log_dir(config: dict) -> Path:
    path = config.get("paths", {}).get("libreqos_apply_log_dir")
    if not path:
        path = "/opt/lqosync/logs/libreqos_apply"
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_libreqos_update(config: dict):
    """Run the LibreQoS apply hook and save per-run stdout/stderr/timing logs.

    Supports two modes:
      direct        - run inside the current namespace/container/host
      host_nsenter  - Docker host-integrated mode; enter host namespaces and run host Python

    host_nsenter requires docker compose with: privileged: true, pid: host, network_mode: host.
    """
    lib = config.get("libreqos", {})
    cmd = lib.get("cmd", "/opt/libreqos/src/LibreQoS.py")
    args = lib.get("args", ["--updateonly"])
    timeout = int(lib.get("timeout_seconds", 300))
    requested_mode = os.getenv("LQOSYNC_RUN_MODE") or lib.get("run_mode") or "direct"
    mode = str(requested_mode).strip().lower()
    use_sudo = _truthy(os.getenv("LQOSYNC_USE_SUDO"), bool(lib.get("sudo", True)))
    # LibreQoS.py reads some files by relative name (e.g. ShapedDevices.csv and
    # ShapedDevices.lastLoaded.csv). The working directory is therefore not
    # optional. Prefer explicit config/env, then fall back to the directory that
    # contains the configured LibreQoS.py command.
    configured_wd = os.getenv("LQOSYNC_LIBREQOS_WORKING_DIR") or lib.get("working_dir")
    if configured_wd:
        working_dir = str(configured_wd)
    else:
        try:
            working_dir = str(Path(str(cmd)).resolve().parent) if str(cmd).endswith(".py") else "/opt/libreqos/src"
        except Exception:
            working_dir = "/opt/libreqos/src"
    if not Path(working_dir).is_absolute():
        working_dir = "/opt/libreqos/src"

    forced_direct_reason = None
    if mode == "host_nsenter" and _is_baremetal_mode():
        # Bare-metal/systemd installs must never use nsenter. It causes errors like:
        #   nsenter: cannot open /proc/1/ns/ipc: Permission denied
        # Direct + sudo is the correct path for /opt/lqosync running beside /opt/libreqos.
        mode = "direct"
        use_sudo = True
        forced_direct_reason = "baremetal_forced_direct"

    # LibreQoS.py uses some relative filenames internally (for example
    # ShapedDevices.csv and ShapedDevices.lastLoaded.csv). Always run it from
    # libreqos.working_dir. In direct/bare-metal mode, fail early with a clear
    # error if the working directory is invalid instead of producing a confusing
    # FileNotFoundError from inside LibreQoS.py.
    if mode != "host_nsenter":
        wd_path = Path(working_dir)
        if not wd_path.exists() or not wd_path.is_dir():
            started_dt = datetime.now(timezone.utc)
            run_id = started_dt.strftime("%Y%m%d_%H%M%S_%f")
            apply_dir = _apply_log_dir(config)
            stderr = f"Invalid libreqos.working_dir: {working_dir}. Expected /opt/libreqos/src containing LibreQoS.py and ShapedDevices.csv."
            meta = {
                "run_id": run_id,
                "started_at": started_dt.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 0,
                "duration_seconds": 0,
                "exit_code": -1,
                "ok": False,
                "timed_out": False,
                "error": stderr,
                "command": [],
                "working_dir": working_dir,
                "mode": mode,
                "requested_mode": requested_mode,
                "forced_direct_reason": forced_direct_reason,
                "stdout_path": str(apply_dir / f"{run_id}.stdout.log"),
                "stderr_path": str(apply_dir / f"{run_id}.stderr.log"),
            }
            try:
                (apply_dir / f"{run_id}.stdout.log").write_text("", encoding="utf-8")
                (apply_dir / f"{run_id}.stderr.log").write_text(stderr, encoding="utf-8")
                (apply_dir / f"{run_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except Exception:
                pass
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": stderr,
                "command": [],
                "working_dir": working_dir,
                "mode": mode,
                "duration_ms": 0,
                "duration_seconds": 0,
                "run_id": run_id,
                "meta": meta,
            }

    if mode == "host_nsenter":
        nsenter = os.getenv("NSENTER_BIN", "/usr/bin/nsenter")
        host_python = os.getenv("HOST_PYTHON", "/usr/bin/python3")
        if str(cmd).endswith(".py"):
            inner = "cd {wd} && exec {py} {cmd} {args}".format(
                wd=shlex.quote(str(working_dir)),
                py=shlex.quote(str(host_python)),
                cmd=shlex.quote(str(cmd)),
                args=" ".join(shlex.quote(str(a)) for a in args),
            )
        else:
            inner = "cd {wd} && exec {cmd} {args}".format(
                wd=shlex.quote(str(working_dir)),
                cmd=shlex.quote(str(cmd)),
                args=" ".join(shlex.quote(str(a)) for a in args),
            )
        command = [nsenter, "-t", "1", "-m", "-u", "-n", "-i", "--", "/bin/bash", "-lc", inner]
    else:
        command = []
        if use_sudo:
            command.append("/usr/bin/sudo")
        if str(cmd).endswith(".py"):
            command.extend([sys.executable if not use_sudo else "/usr/bin/python3", cmd])
        else:
            command.append(cmd)
        command.extend(args)

    apply_dir = _apply_log_dir(config)
    started_dt = datetime.now(timezone.utc)
    run_id = started_dt.strftime("%Y%m%d_%H%M%S_%f")
    t0 = time.perf_counter()
    stdout = ""
    stderr = ""
    exit_code = -1
    ok = False
    timed_out = False
    error = None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=working_dir if mode != "host_nsenter" else None)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        exit_code = result.returncode
        ok = result.returncode == 0
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or "LibreQoS update timed out"
        exit_code = -1
        timed_out = True
        ok = False
    except Exception as e:
        stderr = str(e)
        exit_code = -1
        error = str(e)
        ok = False
    duration_ms = int((time.perf_counter() - t0) * 1000)
    finished_dt = datetime.now(timezone.utc)

    meta = {
        "run_id": run_id,
        "started_at": started_dt.isoformat(),
        "finished_at": finished_dt.isoformat(),
        "duration_ms": duration_ms,
        "duration_seconds": round(duration_ms / 1000, 3),
        "exit_code": exit_code,
        "ok": ok,
        "timed_out": timed_out,
        "error": error,
        "command": command,
        "working_dir": working_dir,
        "mode": mode,
        "requested_mode": requested_mode,
        "forced_direct_reason": forced_direct_reason,
        "stdout_path": str(apply_dir / f"{run_id}.stdout.log"),
        "stderr_path": str(apply_dir / f"{run_id}.stderr.log"),
    }
    try:
        (apply_dir / f"{run_id}.stdout.log").write_text(stdout, encoding="utf-8")
        (apply_dir / f"{run_id}.stderr.log").write_text(stderr, encoding="utf-8")
        (apply_dir / f"{run_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {
        "ok": ok,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "working_dir": working_dir,
        "mode": mode,
        "duration_ms": duration_ms,
        "duration_seconds": round(duration_ms / 1000, 3),
        "run_id": run_id,
        "meta": meta,
    }
