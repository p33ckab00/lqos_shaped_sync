"""Config schema validation, migration, and health scoring for LQoSync.

v2.51 adds a lightweight schema layer around config.json. It does not replace
existing config_loader validation; it complements it with versioned migrations,
policy-setting validation, and operator-readable health scoring for Config
Center / Setup & Repair.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from engine.policy_defaults import CLEANUP_ACTIONS, POLICY_PRESETS, smart_policy_defaults
from engine.policy_schema import POLICY_SCHEMA, get_by_path, normalize_policies
from rules.network_mode import VALID_NETWORK_MODES

CONFIG_SCHEMA_VERSION = 5


def deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def migrate_config_schema(cfg: dict) -> tuple[dict, list[str]]:
    """Return a migrated copy and a list of migration notes.

    Migrations are conservative: missing keys are added, operator-defined values
    are preserved, and invalid values are reported by validation rather than
    aggressively rewritten.
    """
    migrated = deepcopy(cfg or {})
    notes: list[str] = []
    old_version = int(migrated.get("config_schema_version") or 1)
    if old_version < CONFIG_SCHEMA_VERSION:
        migrated["config_schema_version"] = CONFIG_SCHEMA_VERSION
        notes.append(f"config_schema_version {old_version} → {CONFIG_SCHEMA_VERSION}")
    if "policies" not in migrated or not isinstance(migrated.get("policies"), dict):
        migrated["policies"] = smart_policy_defaults()
        notes.append("Added missing policies block")
    else:
        before = deepcopy(migrated["policies"])
        normalize_policies(migrated)
        if before != migrated.get("policies"):
            notes.append("Merged missing Smart Policy defaults")
    migrated.setdefault("config_validation", {})
    migrated["config_validation"].setdefault("schema_version", CONFIG_SCHEMA_VERSION)
    migrated["config_validation"].setdefault("validate_before_save", True)
    migrated["config_validation"].setdefault("simulate_before_save", True)
    return migrated, notes


def validate_schema(cfg: dict) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if int(cfg.get("config_schema_version") or 0) < CONFIG_SCHEMA_VERSION:
        warnings.append(f"config_schema_version is older than expected v{CONFIG_SCHEMA_VERSION}")
        recommendations.append("Open Config Center and save once to persist migrated schema defaults.")

    if cfg.get("network_mode") not in VALID_NETWORK_MODES:
        errors.append(f"network_mode invalid: {cfg.get('network_mode')}")

    app = cfg.get("app", {}) or {}
    if app.get("auto_apply") and not app.get("backup_before_apply", True):
        warnings.append("auto_apply is enabled while backup_before_apply is disabled")
        recommendations.append("Enable backup_before_apply before live auto-apply.")

    paths = cfg.get("paths", {}) or {}
    for key in ("shaped_devices_csv", "network_json", "runtime_state", "policy_state", "audit_log"):
        if not paths.get(key):
            errors.append(f"paths.{key} is required")
        elif key in {"shaped_devices_csv", "network_json"} and not Path(str(paths[key])).is_absolute():
            errors.append(f"paths.{key} must be absolute")

    lib = cfg.get("libreqos", {}) or {}
    wd = str(lib.get("working_dir") or "")
    if not wd:
        errors.append("libreqos.working_dir is required")
    elif not Path(wd).is_absolute():
        errors.append("libreqos.working_dir must be absolute")
    if lib.get("run_mode") not in {"direct", "host_nsenter"}:
        errors.append(f"libreqos.run_mode invalid: {lib.get('run_mode')}")

    policies = cfg.get("policies", {}) or {}
    if policies.get("mode") not in POLICY_PRESETS:
        errors.append(f"policies.mode invalid: {policies.get('mode')}")

    for item in POLICY_SCHEMA:
        path = item["path"]
        value = get_by_path(cfg, path, None)
        if value is None:
            warnings.append(f"Missing policy setting: {path}")
            continue
        typ = item.get("type")
        if typ == "bool" and not isinstance(value, bool):
            errors.append(f"{path} must be true/false")
        if typ == "number":
            try:
                num = float(value)
                if item.get("min") is not None and num < float(item["min"]):
                    errors.append(f"{path} must be >= {item['min']}")
                if item.get("max") is not None and num > float(item["max"]):
                    errors.append(f"{path} must be <= {item['max']}")
            except Exception:
                errors.append(f"{path} must be numeric")
        choices = item.get("choices") or []
        if choices and value not in choices:
            errors.append(f"{path} invalid: {value}; allowed: {', '.join(map(str, choices))}")

    # Additional cleanup action checks for any action-like keys not covered by schema.
    def walk(obj: Any, prefix: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else k
                if k.endswith("_action") or k.endswith("action"):
                    if isinstance(v, str) and v not in CLEANUP_ACTIONS:
                        errors.append(f"{path} invalid action: {v}")
                walk(v, path)
    walk(policies, "policies")

    health = config_health_score(errors, warnings)
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
        "health_score": health["score"],
        "health_level": health["level"],
    }


def config_health_score(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    score = 100 - (len(errors) * 20) - (len(warnings) * 5)
    score = max(0, min(100, score))
    if score >= 90:
        level = "excellent"
    elif score >= 75:
        level = "good"
    elif score >= 50:
        level = "warning"
    else:
        level = "critical"
    return {"score": score, "level": level}
