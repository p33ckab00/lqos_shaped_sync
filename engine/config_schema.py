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

CONFIG_SCHEMA_VERSION = 10


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
    # Schema-owned defaults that must exist even when a preserved older
    # config.json bypasses the full config_loader DEFAULT_CONFIG merge. Keep
    # these fragments local to avoid circular imports with config_loader.
    default_fragments = {
        "app": {
            "name": "LQoSync",
            "operation_mode": "automatic",
            "auto_apply": True,
            "dry_run_default": False,
            "backup_before_apply": False,
            "backup_retention": 10,
            "file_drift_policy": "overwrite_with_backup",
        },
        "notifications": {
            "enabled": True,
            "internal_center_enabled": True,
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
                "base_url": "",
                "parse_mode": "HTML",
                "timeout_seconds": 10,
                "notify_levels": ["critical", "warning"],
                "minimum_interval_seconds": 60,
                "dedupe_window_minutes": 60,
                "max_items_per_digest": 10,
                "send_digest": True,
                "send_individual": False,
                "notify_on_apply_failed": True,
                "notify_on_policy_block": True,
                "notify_on_confirmation_required": True,
                "notify_on_update_available": True,
                "notify_on_source_health_warning": True,
                "notify_on_performance_slow": True,
            },
        },
        "setup_wizard": {
            "enabled": True,
            "first_run_completed": False,
            "redirect_after_login_until_complete": True,
            "show_dashboard_banner_until_complete": True,
            "scheduler_enable_requires_dry_run": True,
            "scheduler_enable_requires_no_failed_checks": True,
            "scheduler_enable_requires_router_and_source": True,
            "allow_force_scheduler_enable": False,
            "recommended_start_page": "/setup-wizard",
        },
        "package_quality": {
            "enabled": True,
            "check_routes_templates": True,
            "check_config_defaults": True,
            "show_in_setup_repair": True,
            "doctor_script": "/opt/lqosync/scripts/lqosync-doctor.sh",
            "release_check_script": "/opt/lqosync/scripts/release_check.py",
            "regression_check_script": "/opt/lqosync/scripts/regression_check.py",
            "config_migration_check_script": "/opt/lqosync/scripts/config_migration_check.py",
            "policy_path_audit_script": "/opt/lqosync/scripts/policy_path_audit.py",
            "stable_release_check_script": "/opt/lqosync/scripts/stable_release_check.py",
            "cleanup_stale_files_script": "/opt/lqosync/scripts/cleanup_stale_files.py",
        },
        "stable_release": {
            "target": "v2.70 Stable Release Candidate",
            "feature_freeze": True,
            "allow_new_sidebar_modules": False,
            "require_release_check": True,
            "require_regression_check": True,
            "require_config_migration_check": True,
            "require_policy_path_audit": True,
            "require_stable_release_check": True,
            "compatibility_routes": ["/health", "/services", "/logs", "/policy", "/notifications", "/routers"],
        },
        "production_readiness": {
            "enabled": True,
            "show_on_dashboard": True,
            "api_enabled": True,
            "excellent_score": 95,
            "warning_score": 85,
            "review_score": 70,
            "block_scheduler_when_not_ready": False,
            "checks": {
                "config_validity": True,
                "setup_wizard": True,
                "dry_run": True,
                "router_sources": True,
                "backup_before_apply": True,
                "libreqos_paths": True,
                "policy_conflicts": True,
                "dashboard_health": True,
                "apply_health": True,
                "service_health": True,
            },
        },
        "access_control": {
            "enabled": True,
            "roles": {
                "owner": "Full control including users, updates, setup/repair, config, policies, backups, and live actions.",
                "admin": "Config, policies, scheduler, backups, operations, and live apply actions except owner-only user/update controls.",
                "operator": "Monitoring, dry-run/reports, lifecycle, operations inspection, and documentation access.",
                "viewer": "Read-only dashboards, devices, reports, docs, and status pages.",
            },
            "owner_required_routes": ["/settings/users", "/updates", "/setup-repair/repair-defaults", "/api/release/integrity"],
            "admin_required_summary": "Config, policy, scheduler, backup restore/delete, service restart, force apply, and setup actions require admin or owner.",
            "operator_summary": "Operators can view operational pages and run dry-run style previews, but cannot change production configuration or perform destructive actions.",
        },
        "config_validation": {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "validate_before_save": True,
            "simulate_before_save": True,
            "show_config_health": True,
            "block_save_on_schema_errors": True,
        },
    }
    for key, defaults in default_fragments.items():
        before = deepcopy(migrated.get(key, {}))
        if not isinstance(migrated.get(key), dict):
            migrated[key] = deepcopy(defaults)
            notes.append(f"Added missing {key} block")
        else:
            migrated[key] = deep_merge(defaults, migrated.get(key, {}))
            if before != migrated[key]:
                notes.append(f"Merged missing {key} defaults")
    migrated.setdefault("config_validation", {})
    migrated["config_validation"]["schema_version"] = CONFIG_SCHEMA_VERSION
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
    operation_mode = str(app.get("operation_mode") or "automatic").strip().lower()
    if operation_mode not in {"automatic", "manual"}:
        errors.append(f"app.operation_mode invalid: {operation_mode}")
    if operation_mode == "automatic" and not app.get("auto_apply", True):
        errors.append("app.auto_apply is required when app.operation_mode is automatic")
        recommendations.append("Enable app.auto_apply or change app.operation_mode to manual.")

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
