import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _truthy(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _running_in_container() -> bool:
    return Path("/.dockerenv").exists() or bool(os.getenv("container"))


def host_control_mode() -> str:
    mode = (os.getenv("HOST_CONTROL_MODE") or "direct").strip().lower()
    install_mode = (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower()
    if install_mode in {"baremetal", "host", "systemd"} or _truthy(os.getenv("LQOSYNC_FORCE_DIRECT"), False):
        return "direct"
    if mode == "nsenter" and install_mode not in {"docker", "container"} and not _running_in_container():
        return "direct"
    return mode


def systemctl_base_command() -> list[str]:
    systemctl = shutil.which("systemctl") or "/bin/systemctl"
    if host_control_mode() == "nsenter":
        nsenter = os.getenv("NSENTER_BIN", "/usr/bin/nsenter")
        return [nsenter, "-t", "1", "-m", "-u", "-n", "-i", "--", systemctl]
    return [systemctl]


def journalctl_base_command() -> list[str]:
    journalctl = shutil.which("journalctl") or "/bin/journalctl"
    if host_control_mode() == "nsenter":
        nsenter = os.getenv("NSENTER_BIN", "/usr/bin/nsenter")
        return [nsenter, "-t", "1", "-m", "-u", "-n", "-i", "--", journalctl]
    return [journalctl]


def sudo_prefix() -> list[str]:
    if host_control_mode() == "nsenter":
        return []
    sudo = shutil.which("sudo") or "/usr/bin/sudo"
    return [sudo]


def services_config(config: dict) -> dict:
    svc = config.setdefault("services", {})
    svc.setdefault("units", [
        "lqosd",
        "lqos_scheduler",
        "lqosync",
    ])
    svc.setdefault("legacy_optional_units", ["lqos_node_manager"])
    svc.setdefault("show_legacy_optional_not_installed", False)
    svc.setdefault("unit_metadata", {
        "lqosd": {"label": "LibreQoS daemon", "role": "required", "note": "Main LibreQoS daemon; newer installs may serve Web UI here."},
        "lqos_scheduler": {"label": "LibreQoS scheduler", "role": "required", "note": "LibreQoS scheduler/integration refresh service."},
        "lqos_node_manager": {"label": "Legacy Web UI service", "role": "legacy_optional", "note": "Older LibreQoS installs only; newer installs usually use lqosd for the Web UI."},
        "lqosync": {"label": "LQoSync service", "role": "required", "note": "LQoSync dashboard and sync engine."},
    })
    svc.setdefault("restart_groups", {
        "libreqos_core": ["lqosd", "lqos_scheduler"],
    })
    svc.setdefault("journal_lines_default", 100)
    return svc


def allowed_units(config: dict) -> set[str]:
    svc = services_config(config)
    units = set(svc.get("units") or [])
    units.update(svc.get("legacy_optional_units") or [])
    for group_units in (svc.get("restart_groups") or {}).values():
        units.update(group_units or [])
    return {u for u in units if isinstance(u, str) and u.strip()}


def service_meta(config: dict, service: str) -> dict[str, Any]:
    svc = services_config(config)
    meta = (svc.get("unit_metadata") or {}).get(service, {})
    role = meta.get("role") or ("legacy_optional" if service in (svc.get("legacy_optional_units") or []) else "required")
    return {
        "label": meta.get("label") or service,
        "role": role,
        "note": meta.get("note") or "",
        "legacy_optional": role == "legacy_optional" or service in (svc.get("legacy_optional_units") or []),
    }


def allowed_groups(config: dict) -> dict[str, list[str]]:
    svc = services_config(config)
    groups = {}
    for name, units in (svc.get("restart_groups") or {}).items():
        clean = [u for u in (units or []) if u in allowed_units(config)]
        groups[name] = clean
    return groups


def service_status(config: dict, service: str) -> dict[str, Any]:
    if service not in allowed_units(config):
        return {"unit": service, "allowed": False, "active": "not_allowed", "load": "unknown", "sub": "unknown", "description": ""}
    meta = service_meta(config, service)
    data = {"unit": service, "allowed": True, "active": "unknown", "load": "unknown", "sub": "unknown", "description": "", **meta}
    try:
        res = subprocess.run(
            systemctl_base_command() + ["show", service, "--property=LoadState,ActiveState,SubState,Description", "--no-pager"],
            capture_output=True, text=True, timeout=12,
        )
        if res.returncode != 0 and not res.stdout.strip():
            data["active"] = "unknown"
            data["stderr"] = res.stderr.strip()
            return data
        props = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
        data["load"] = props.get("LoadState") or "unknown"
        data["active"] = props.get("ActiveState") or "unknown"
        data["sub"] = props.get("SubState") or "unknown"
        data["description"] = props.get("Description") or ""
        data["installed"] = data["load"] != "not-found"
        if data.get("legacy_optional") and not data["installed"]:
            data["active"] = "not_installed"
            data["sub"] = "legacy_optional"
    except Exception as e:
        data["stderr"] = str(e)
    return data


def all_service_status(config: dict) -> dict[str, dict[str, Any]]:
    svc_cfg = services_config(config)
    show_missing_optional = _truthy(svc_cfg.get("show_legacy_optional_not_installed"), False)
    result: dict[str, dict[str, Any]] = {}
    # Show configured/current units first. Optional legacy units are auto-detected
    # and only displayed when installed unless explicitly configured to show them.
    ordered = []
    for unit in list(svc_cfg.get("units") or []) + list(svc_cfg.get("legacy_optional_units") or []):
        if unit not in ordered:
            ordered.append(unit)
    for svc in ordered:
        status = service_status(config, svc)
        if status.get("legacy_optional") and not status.get("installed") and not show_missing_optional:
            continue
        result[svc] = status
    return result


def restart_units(config: dict, units: list[str]) -> dict[str, Any]:
    allowed = allowed_units(config)
    clean = [u for u in units if u in allowed]
    if not clean:
        return {"ok": False, "units": units, "stdout": "", "stderr": "No allowed units to restart", "returncode": -1}
    command = sudo_prefix() + systemctl_base_command() + ["restart"] + clean
    started = datetime.now(timezone.utc)
    try:
        res = subprocess.run(command, capture_output=True, text=True, timeout=90)
        return {
            "ok": res.returncode == 0,
            "units": clean,
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
            "returncode": res.returncode,
            "command": command,
            "started_at": started.isoformat(),
            "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }
    except Exception as e:
        return {"ok": False, "units": clean, "stdout": "", "stderr": str(e), "returncode": -1, "command": command, "started_at": started.isoformat()}


def restart_service(config: dict, service: str) -> dict[str, Any]:
    return restart_units(config, [service])


def restart_group(config: dict, group_name: str) -> dict[str, Any]:
    groups = allowed_groups(config)
    if group_name not in groups:
        return {"ok": False, "group": group_name, "stdout": "", "stderr": "Restart group not allowed", "returncode": -1}
    result = restart_units(config, groups[group_name])
    result["group"] = group_name
    return result


def journal_lines(config: dict, service: str, lines: int = 100) -> dict[str, Any]:
    if service not in allowed_units(config):
        return {"ok": False, "unit": service, "stdout": "", "stderr": "service not allowed"}
    lines = max(1, min(int(lines or 100), 1000))
    command = journalctl_base_command() + ["-u", service, "-n", str(lines), "--no-pager", "-o", "short-iso"]
    try:
        res = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return {"ok": res.returncode == 0, "unit": service, "stdout": res.stdout or "", "stderr": res.stderr or "", "returncode": res.returncode, "command": command}
    except Exception as e:
        return {"ok": False, "unit": service, "stdout": "", "stderr": str(e), "returncode": -1, "command": command}


def list_apply_runs(config: dict, limit: int = 20) -> list[dict[str, Any]]:
    apply_dir = Path(config.get("paths", {}).get("libreqos_apply_log_dir", "/opt/LQoSync/logs/libreqos_apply"))
    if not apply_dir.exists():
        return []
    runs = []
    for meta_file in sorted(apply_dir.glob("*.json"), reverse=True):
        try:
            import json
            runs.append(json.loads(meta_file.read_text(encoding="utf-8")))
        except Exception:
            pass
        if len(runs) >= limit:
            break
    return runs


def read_apply_file(config: dict, run_id: str, stream: str) -> str:
    apply_dir = Path(config.get("paths", {}).get("libreqos_apply_log_dir", "/opt/LQoSync/logs/libreqos_apply"))
    suffix = "stdout.log" if stream == "stdout" else "stderr.log"
    target = apply_dir / f"{run_id}.{suffix}"
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="ignore")
