#!/usr/bin/env python3
"""Validate that config.json.example contains mandatory production defaults."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config.json.example"

required = {
    ("libreqos", "cmd"): "/opt/libreqos/src/LibreQoS.py",
    ("libreqos", "working_dir"): "/opt/libreqos/src",
    ("libreqos", "run_mode"): "direct",
    ("libreqos", "sudo"): True,
    ("libreqos", "run_only_when_files_changed"): True,
    ("libreqos", "retry_if_last_apply_failed"): True,
    ("paths", "shaped_devices_csv"): "/opt/libreqos/src/ShapedDevices.csv",
    ("paths", "network_json"): "/opt/libreqos/src/network.json",
    ("paths", "backup_dir"): "/opt/LQoSync/backups",
    ("paths", "runtime_state"): "/opt/LQoSync/state/runtime_state.json",
    ("paths", "collector_cache"): "/opt/LQoSync/state/collector_cache.json",
    ("collector", "selective_fields"): True,
    ("collector", "dhcp", "lease_mode"): "permissive",
    ("collector", "hotspot", "enhanced_metadata"): True,
}

def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    errors = []
    for keys, expected in required.items():
        cur = data
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                errors.append(f"missing {'.'.join(keys)}")
                cur = None
                break
            cur = cur[key]
        if cur is not None and cur != expected:
            errors.append(f"{'.'.join(keys)} expected {expected!r}, got {cur!r}")
    if data.get("network_mode") != "router_children" or data.get("flat_network") is not False or data.get("no_parent") is not False:
        errors.append("default network mode must be router_children with flat_network=false and no_parent=false")
    if errors:
        print("config.json.example validation failed:")
        for e in errors:
            print(" -", e)
        return 1
    print("config.json.example validation passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
