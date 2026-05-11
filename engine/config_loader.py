import json
import os
from copy import deepcopy
from pathlib import Path
from applier.atomic_writer import atomic_write_text
from rules.network_mode import normalize_network_mode, VALID_NETWORK_MODES
from datetime import datetime, timezone
import shutil

DEFAULT_CONFIG = {
    "network_mode": "router_children",
    "flat_network": False,
    "no_parent": False,
    "preserve_network_config": False,
    "app": {
        "name": "LQoSync",
        "auto_apply": True,
        "dry_run_default": False,
        "backup_before_apply": True,
        "backup_retention": 30,
        "file_drift_policy": "overwrite_with_backup",  # overwrite_with_backup | warn_only | block
    },
    "paths": {
        "shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv",
        "network_json": "/opt/libreqos/src/network.json",
        "backup_dir": "/opt/lqosync/backups",
        "log_file": "/opt/lqosync/logs/lqos_shaped_sync.log",
        "runtime_state": "/opt/lqosync/state/runtime_state.json",
        "lock_file": "/opt/lqosync/state/lqosync.lock",
        "audit_log": "/opt/lqosync/logs/audit.jsonl",
        "libreqos_apply_log_dir": "/opt/lqosync/logs/libreqos_apply",
        "collector_cache": "/opt/lqosync/state/collector_cache.json",
    },
    "libreqos": {
        "cmd": "/opt/libreqos/src/LibreQoS.py",
        "args": ["--updateonly"],
        "working_dir": "/opt/libreqos/src",
        "timeout_seconds": 300,
        "run_only_when_files_changed": True,
        "retry_if_last_apply_failed": True,
        "sudo": True,
        "run_mode": "direct",
    },
    "scheduler": {
        "enabled": False,
        "active_interval_seconds": 30,
        "idle_interval_seconds": 120,
        "error_retry_interval_seconds": 30,
        "apply_cooldown_seconds": 20,
        "max_instances": 1,
    },
    "defaults": {
        "id_length": 8,
        "min_rate_percentage": 0.5,
        "default_pppoe_profile": "default",
        "default_pppoe_rate": "10M/10M",
        "default_dhcp_per_client_mbps": 15,
        "default_hotspot_per_client_mbps": 10,
        "duplicate_ip_policy": "warn_and_skip",
        "static_comment_value": "static",
    },
    "collector": {
        "selective_fields": True,
        "pppoe": {
            "read_active": True,
            "read_secrets": True,
            "read_profiles": True,
        },
        "dhcp": {
            "lease_mode": "permissive",
            "read_server_metadata": True,
        },
        "hotspot": {
            "enhanced_metadata": True,
        },
    },
    "preflight": {
        "enabled": True,
        "duplicate_ip_policy": "warn_and_skip",
        "missing_parent_policy": "block",
        "invalid_bandwidth_policy": "block",
    },
    "ui": {
        "refresh_seconds": 5,
        "show_raw_json_editor": True,
        "default_theme": "light",
        "privacy_mode_available": True,
    },
    "topology": {
        "allow_deep_hierarchy": True,
        "allow_custom_edit": True,
        "show_virtual_nodes": True,
        "validate_before_save": True,
    },
    "services": {
        # Required/current LibreQoS + LQoSync units. lqos_node_manager is not
        # required on newer LibreQoS installs and is tracked separately as a
        # legacy optional Web UI unit.
        "units": ["lqosd", "lqos_scheduler", "lqos_shaped_sync"],
        "legacy_optional_units": ["lqos_node_manager"],
        "show_legacy_optional_not_installed": False,
        "unit_metadata": {
            "lqosd": {
                "label": "LibreQoS daemon",
                "role": "required",
                "note": "Main LibreQoS daemon; on newer LibreQoS installs this also serves the Web UI on port 9123."
            },
            "lqos_scheduler": {
                "label": "LibreQoS scheduler",
                "role": "required",
                "note": "Runs LibreQoS scheduler/integration refresh jobs."
            },
            "lqos_node_manager": {
                "label": "Legacy Web UI service",
                "role": "legacy_optional",
                "note": "Older LibreQoS installs only. Newer LibreQoS usually exposes Web UI through lqosd, so this unit may be not installed."
            },
            "lqos_shaped_sync": {
                "label": "LQoSync service",
                "role": "required",
                "note": "LQoSync dashboard, scheduler, and MikroTik-to-LibreQoS sync engine."
            }
        },
        "restart_groups": {
            "libreqos_core": ["lqosd", "lqos_scheduler"]
        },
        "journal_lines_default": 100
    },
    "routers": [],
}


def deep_merge(base, override):
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None):
    path = path or os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
    p = Path(path)
    if not p.exists():
        cfg = deepcopy(DEFAULT_CONFIG)
        normalize_config(cfg)
        return cfg
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = deep_merge(DEFAULT_CONFIG, raw)
    normalize_config(cfg)
    return cfg


def _backup_config_file(path: str):
    p = Path(path)
    if not p.exists():
        return None
    backup_dir = p.parent / "config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"config.json.{stamp}.bak"
    shutil.copy2(p, dst)
    return str(dst)


def save_config(config, path=None, backup_existing=True):
    path = path or os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
    cfg = deep_merge(DEFAULT_CONFIG, config)
    normalize_config(cfg)
    errors, _warnings = validate_config(cfg)
    if errors:
        raise ValueError("Invalid config: " + "; ".join(errors))
    if backup_existing:
        try:
            _backup_config_file(path)
        except Exception:
            # Config save should not fail just because a safety backup failed.
            pass
    text = json.dumps(cfg, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    atomic_write_text(path, text)
    try:
        Path(path).chmod(0o600)
    except Exception:
        pass


def _floatish(value, default):
    try:
        return float(value)
    except Exception:
        return default


def normalize_config(cfg):
    cfg.setdefault("app", {})
    cfg.setdefault("paths", {})
    cfg.setdefault("libreqos", {})
    cfg.setdefault("scheduler", {})
    cfg.setdefault("defaults", {})
    cfg.setdefault("collector", {})
    cfg.setdefault("topology", {})
    cfg.setdefault("preflight", {})
    cfg.setdefault("routers", [])

    # Merge nested defaults without dropping user values.
    merged = deep_merge(DEFAULT_CONFIG, cfg)
    cfg.clear(); cfg.update(merged)

    # Network mode is the user-facing layout selector. Legacy flags are derived
    # automatically so old config.json files keep working.
    normalize_network_mode(cfg)

    # LibreQoS.py uses relative files internally, so working_dir must be set
    # explicitly. Preserve operator value if absolute; otherwise normalize.
    lib = cfg.setdefault("libreqos", {})
    wd = str(lib.get("working_dir") or "").strip()
    if not wd or not Path(wd).is_absolute():
        lib["working_dir"] = str(Path(os.getenv("LQOSYNC_LIBREQOS_SRC") or "/opt/libreqos/src"))
    lib.setdefault("retry_if_last_apply_failed", True)
    install_mode = (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower()
    force_direct = str(os.getenv("LQOSYNC_FORCE_DIRECT") or "").strip().lower() in {"1", "true", "yes", "on"}
    running_in_container = Path("/.dockerenv").exists() or bool(os.getenv("container"))
    # Bare-metal/systemd is the priority deployment. If LQoSync is not running
    # in a container, host_nsenter is invalid and must not survive through config
    # normalization. This protects live installs even when an old config.json or
    # config.json.example contained Docker-specific values.
    if install_mode in {"baremetal", "host", "systemd"} or force_direct or (install_mode not in {"docker", "container"} and not running_in_container):
        lib["run_mode"] = "direct"
        lib["sudo"] = True

    # Normalize LibreQoS service unit names. Older builds used lqos/lqosd_scheduler,
    # but the correct/common LibreQoS units for status/restart are lqosd and
    # lqos_scheduler, e.g. `sudo systemctl status lqosd lqos_scheduler`.
    svc = cfg.setdefault("services", {})
    aliases = {"lqos": "lqosd", "lqosd_scheduler": "lqos_scheduler"}
    units = svc.get("units") or DEFAULT_CONFIG["services"]["units"]
    normalized_units = []
    for unit in units:
        unit = aliases.get(str(unit).strip(), str(unit).strip())
        if unit and unit not in normalized_units:
            normalized_units.append(unit)
    # Add and normalize optional/legacy service metadata. Keep legacy units out
    # of the required list by default so fresh installs do not show
    # lqos_node_manager as a required/failed service.
    legacy_optional = svc.get("legacy_optional_units") or DEFAULT_CONFIG["services"].get("legacy_optional_units", [])
    svc["legacy_optional_units"] = []
    for unit in legacy_optional:
        unit = aliases.get(str(unit).strip(), str(unit).strip())
        if unit and unit not in svc["legacy_optional_units"]:
            svc["legacy_optional_units"].append(unit)
    svc.setdefault("show_legacy_optional_not_installed", DEFAULT_CONFIG["services"].get("show_legacy_optional_not_installed", False))
    svc.setdefault("unit_metadata", {})
    svc["unit_metadata"] = deep_merge(DEFAULT_CONFIG["services"].get("unit_metadata", {}), svc.get("unit_metadata", {}))
    # If an old config inherited lqos_node_manager from previous defaults, it is
    # still allowed/auto-detected, but treated as legacy optional in UI/status.
    svc["units"] = normalized_units
    groups = svc.get("restart_groups") or DEFAULT_CONFIG["services"]["restart_groups"]
    normalized_groups = {}
    for name, group_units in groups.items():
        clean = []
        for unit in group_units or []:
            unit = aliases.get(str(unit).strip(), str(unit).strip())
            if unit and unit not in clean:
                clean.append(unit)
        normalized_groups[name] = clean
    svc["restart_groups"] = normalized_groups

    for router in cfg.get("routers", []):
        router.setdefault("enabled", True)
        router.setdefault("name", "Router")
        router.setdefault("address", "")
        router.setdefault("port", 8728)
        router.setdefault("username", "")
        router.setdefault("password", "")
        router.setdefault("root_download_mbps", cfg.get("ROOT_DOWNLOAD_MBPS", 115))
        router.setdefault("root_upload_mbps", cfg.get("ROOT_UPLOAD_MBPS", 115))
        router.setdefault("root_type", "site")
        router.setdefault("root_virtual", False)
        router.setdefault("parent_node", "")  # used by deep_hierarchy/custom_hierarchy modes

        router.setdefault("pppoe", {})
        pppoe = router["pppoe"]
        pppoe.setdefault("enabled", False)
        pppoe.setdefault("per_plan_node", False)
        pppoe.setdefault("flat_aggregate_factor", 0.3)
        pppoe.setdefault("node_type", "plan")
        pppoe.setdefault("flat_node_name", "PPP-{router}")
        pppoe.setdefault("plan_node_name", "{profile}-{router}")
        pppoe.setdefault("factor_rules", [
            {"max_plan_mbps": 15, "download_factor": 0.31, "upload_factor": 0.31},
            {"max_plan_mbps": 9999, "download_factor": 1.0, "upload_factor": 1.0},
        ])

        router.setdefault("dhcp", {})
        dhcp = router["dhcp"]
        dhcp.setdefault("enabled", False)
        if not dhcp.get("servers") and dhcp.get("dhcp_server"):
            dhcp["servers"] = [{
                "name": name,
                "enabled": True,
                "mode": "per_site",
                "default_plan_down_mbps": dhcp.get("download_limit_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"]),
                "default_plan_up_mbps": dhcp.get("upload_limit_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"]),
                "download_factor": 0.5,
                "upload_factor": 0.5,
                "node_type": "site",
                "node_name": "DHCP-{server}-{router}",
            } for name in dhcp.get("dhcp_server", [])]
        dhcp.setdefault("servers", [])
        for server in dhcp.get("servers", []):
            server.setdefault("enabled", True)
            server.setdefault("name", "")
            server.setdefault("mode", "per_site")
            if "default_plan_down_mbps" not in server and "download_limit_mbps" in server:
                server["default_plan_down_mbps"] = server["download_limit_mbps"]
            if "default_plan_up_mbps" not in server and "upload_limit_mbps" in server:
                server["default_plan_up_mbps"] = server["upload_limit_mbps"]
            server.setdefault("default_plan_down_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"])
            server.setdefault("default_plan_up_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"])
            server.setdefault("download_factor", 0.5)
            server.setdefault("upload_factor", 0.5)
            server.setdefault("node_type", "site")
            server.setdefault("node_name", "DHCP-{server}-{router}" if server.get("mode") == "per_site" else "PLAN-DHCP-{plan}-{router}")
            server.setdefault("speed_comment", "")

        router.setdefault("hotspot", {})
        hs = router["hotspot"]
        hs.setdefault("enabled", False)
        hs.setdefault("include_mac", True)
        hs.setdefault("download_limit_mbps", cfg["defaults"]["default_hotspot_per_client_mbps"])
        hs.setdefault("upload_limit_mbps", cfg["defaults"]["default_hotspot_per_client_mbps"])
        hs.setdefault("download_factor", 1.0)
        hs.setdefault("upload_factor", 1.0)
        hs.setdefault("node_type", "site")
        hs.setdefault("node_name", "HS-{router}")
        hs.setdefault("enhanced_metadata", cfg.get("collector", {}).get("hotspot", {}).get("enhanced_metadata", True))


def validate_config(cfg: dict):
    errors: list[str] = []
    warnings: list[str] = []
    paths = cfg.get("paths", {})
    mode = cfg.get("network_mode")
    if mode not in VALID_NETWORK_MODES:
        errors.append(f"network_mode invalid: {mode}")
    for opt in ("file_drift_policy",):
        val = cfg.get("app", {}).get(opt)
        if val not in ("overwrite_with_backup", "warn_only", "block"):
            errors.append(f"app.{opt} invalid: {val}")
    for key in ("shaped_devices_csv", "network_json"):
        if not paths.get(key):
            errors.append(f"paths.{key} is required")
    topology = cfg.setdefault("topology", {})
    topology.setdefault("allow_deep_hierarchy", True)
    topology.setdefault("allow_custom_edit", True)
    topology.setdefault("show_virtual_nodes", True)
    topology.setdefault("validate_before_save", True)

    collector = cfg.get("collector", {})
    lease_mode = collector.get("dhcp", {}).get("lease_mode", "permissive")
    if lease_mode not in ("permissive", "strict"):
        errors.append(f"collector.dhcp.lease_mode invalid: {lease_mode}")
    sched = cfg.get("scheduler", {})
    for key in ("active_interval_seconds", "idle_interval_seconds", "error_retry_interval_seconds"):
        try:
            if int(sched.get(key, 0)) <= 0:
                errors.append(f"scheduler.{key} must be > 0")
        except Exception:
            errors.append(f"scheduler.{key} must be numeric")
    seen_router_names = set()
    for idx, router in enumerate(cfg.get("routers", [])):
        name = router.get("name") or f"router[{idx}]"
        if name in seen_router_names:
            errors.append(f"duplicate router name: {name}")
        seen_router_names.add(name)
        if router.get("enabled", True):
            if not router.get("address"):
                warnings.append(f"{name}: address is empty")
            if not router.get("username"):
                warnings.append(f"{name}: username is empty")
        try:
            float(router.get("root_download_mbps", 0)); float(router.get("root_upload_mbps", 0))
        except Exception:
            errors.append(f"{name}: root bandwidth must be numeric")
        for rule in router.get("pppoe", {}).get("factor_rules", []):
            for key in ("max_plan_mbps", "download_factor", "upload_factor"):
                try: float(rule.get(key))
                except Exception: errors.append(f"{name}: PPP factor rule {key} must be numeric")
        for server in router.get("dhcp", {}).get("servers", []):
            if not server.get("name"):
                errors.append(f"{name}: DHCP server entry has empty name")
            if str(server.get("mode", "per_site")).lower() not in ("per_site", "per_plan"):
                errors.append(f"{name}/{server.get('name')}: invalid DHCP mode")
            for key in ("default_plan_down_mbps", "default_plan_up_mbps", "download_factor", "upload_factor"):
                try: float(server.get(key))
                except Exception: errors.append(f"{name}/{server.get('name')}: {key} must be numeric")
    return errors, warnings
