#!/usr/bin/env python3
"""Normalize and persist LQoSync config.json during installs/upgrades.

Safe migration goals:
- Keep operator router credentials and service settings.
- Deep-merge missing defaults.
- Ensure LibreQoS apply recovery keys exist.
- For the live /opt/libreqos/src/config.json, normalize LQoSync runtime paths
  to /opt/lqosync so the service does not depend on its current directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.config_loader import load_config, save_config  # noqa: E402


def _normalize_live_paths(cfg: dict) -> None:
    paths = cfg.setdefault("paths", {})
    runtime_base = Path(os.getenv("LQOSYNC_HOME") or "/opt/lqosync")
    libreqos_src = Path(os.getenv("LQOSYNC_LIBREQOS_SRC") or "/opt/libreqos/src")
    defaults = {
        "backup_dir": runtime_base / "backups",
        "log_file": runtime_base / "logs" / "lqosync.log",
        "runtime_state": runtime_base / "state" / "runtime_state.json",
        "lock_file": runtime_base / "state" / "lqosync.lock",
        "audit_log": runtime_base / "logs" / "audit.jsonl",
        "libreqos_apply_log_dir": runtime_base / "logs" / "libreqos_apply",
        "collector_cache": runtime_base / "state" / "collector_cache.json",
        "shaped_devices_csv": libreqos_src / "ShapedDevices.csv",
        "network_json": libreqos_src / "network.json",
    }
    for key, default_path in defaults.items():
        value = str(paths.get(key) or "").strip()
        if not value or not Path(value).is_absolute():
            paths[key] = str(default_path)

    lib = cfg.setdefault("libreqos", {})
    lib.setdefault("cmd", str(libreqos_src / "LibreQoS.py"))
    wd = str(lib.get("working_dir") or "").strip()
    if not wd or not Path(wd).is_absolute():
        lib["working_dir"] = str(libreqos_src)
    lib["retry_if_last_apply_failed"] = bool(lib.get("retry_if_last_apply_failed", True))

    install_mode = (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower()
    force_direct = str(os.getenv("LQOSYNC_FORCE_DIRECT") or "").strip().lower() in {"1", "true", "yes", "on"}
    # Bare-metal/systemd is the priority deployment. It must use direct mode.
    # host_nsenter is only valid for the Docker host-integrated container.
    if install_mode in {"baremetal", "host", "systemd"} or force_direct:
        lib["run_mode"] = "direct"
        lib["sudo"] = True


def main() -> int:
    config_path = os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
    path = Path(config_path)
    if not path.exists():
        print(f"[LQoSync] Config migration skipped; file not found: {config_path}")
        return 0

    cfg = load_config(config_path)
    _normalize_live_paths(cfg)
    # save_config() performs canonical deep-merge + network-mode normalization + validation.
    save_config(cfg, config_path, backup_existing=True)
    print(f"[LQoSync] Config migration complete: {config_path}")
    print("[LQoSync] Ensured libreqos.working_dir=/opt/libreqos/src, retry_if_last_apply_failed=true, and absolute /opt/lqosync runtime paths")
    if (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower() in {"baremetal", "host", "systemd"}:
        print("[LQoSync] Bare-metal mode enforced: libreqos.run_mode=direct, libreqos.sudo=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
