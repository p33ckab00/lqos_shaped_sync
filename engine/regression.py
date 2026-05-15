"""Production hardening and regression checks for LQoSync.

These checks are read-only and intentionally offline. They catch the kinds of
packaging regressions that are easy to miss in a growing Flask project:
missing routes, missing templates, route/template context mismatches,
config-migration gaps, policy behavior drift, Operations Center regressions,
and documentation integrity issues.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from engine.release_integrity import collect_app_routes, collect_render_templates, route_exists


@dataclass
class RegressionItem:
    key: str
    title: str
    status: str  # ok | warn | fail
    detail: str
    category: str = "regression"
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _summary(items: list[RegressionItem]) -> dict[str, int]:
    return {
        "ok": sum(1 for i in items if i.status == "ok"),
        "warn": sum(1 for i in items if i.status == "warn"),
        "fail": sum(1 for i in items if i.status == "fail"),
    }


def _load_example_config(root: Path) -> dict[str, Any]:
    return json.loads((root / "config.json.example").read_text(encoding="utf-8"))


IMPORTANT_ROUTES = {
    "dashboard": "/",
    "shaped_devices": "/devices",
    "network_layout": "/network",
    "dry_run": "/sync/dry-run",
    "config_center": "/config",
    "operations_center": "/operations",
    "reports": "/reports",
    "lifecycle": "/lifecycle",
    "docs_search": "/docs/search",
    "setup_wizard": "/setup-wizard",
    "setup_repair": "/setup-repair",
    "updates": "/updates",
    "users": "/settings/users",
    "health_api": "/api/health/trends",
    "release_integrity_api": "/api/release/integrity",
}


EXPECTED_ROUTE_TEMPLATES = {
    "/": "dashboard.html",
    "/devices": "shaped_devices.html",
    "/network": "network_layout.html",
    "/sync/dry-run": "dry_run.html",
    "/config": "config.html",
    "/operations": "operations.html",
    "/reports": "reports.html",
    "/lifecycle": "lifecycle.html",
    "/docs/search": "docs_search.html",
    "/setup-wizard": "setup_wizard.html",
    "/setup-repair": "setup_repair.html",
    "/updates": "updates.html",
    "/settings/users": "settings_users.html",
    "/about": "about.html",
}


EXPECTED_TEMPLATE_CONTEXTS = {
    "dashboard.html": {"cfg", "state", "services", "git_status", "config_errors", "config_warnings", "health_report", "setup_wizard", "user"},
    "operations.html": {"cfg", "state", "services", "groups", "last", "apply_runs", "apply_pagination", "selected_unit", "lines", "journal_lines_count", "journal", "backups", "backup_pagination", "audit_events", "audit_pagination", "active_tab", "user"},
    "reports.html": {"cfg", "state", "report", "user"},
    "lifecycle.html": {"cfg", "state", "policy_state", "summary", "report", "events", "client_items", "selected_code", "user"},
    "config.html": {"config_json", "config", "config_errors", "config_warnings", "schema_report", "schema_version", "policy_conflicts", "identity_report", "telegram", "initial_tab", "user"},
    "setup_repair.html": {"cfg", "state", "report", "services", "config_errors", "config_warnings", "user"},
    "setup_wizard.html": {"cfg", "state", "report", "wizard", "network_modes", "services", "config_errors", "config_warnings", "user"},
    "network_layout.html": {"network", "node_math", "config", "nodes_flat", "shaped_rows", "user"},
}


def _render_context_map(root: Path) -> dict[str, list[set[str]]]:
    """Map template name to sets of keyword args supplied to render_template."""
    app_py = root / "app.py"
    if not app_py.exists():
        return {}
    tree = ast.parse(app_py.read_text(encoding="utf-8"), filename=str(app_py))
    out: dict[str, list[set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_render = False
        if isinstance(func, ast.Name) and func.id == "render_template":
            is_render = True
        elif isinstance(func, ast.Attribute) and func.attr == "render_template":
            is_render = True
        if not is_render or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys = {kw.arg for kw in node.keywords if kw.arg}
            out.setdefault(arg.value, []).append(keys)
    return out


def check_route_regressions(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[RegressionItem] = []
    routes = collect_app_routes(root)
    rendered = set(collect_render_templates(root))

    missing = [name for name, url in IMPORTANT_ROUTES.items() if not route_exists(url, routes)]
    if missing:
        items.append(RegressionItem("routes.important", "Important WebUI/API routes", "fail", ", ".join(missing), "routes", "Restore the missing Flask route handlers before publishing."))
    else:
        items.append(RegressionItem("routes.important", "Important WebUI/API routes", "ok", f"{len(IMPORTANT_ROUTES)} important routes are present", "routes"))

    route_template_problems = []
    for url, template in EXPECTED_ROUTE_TEMPLATES.items():
        if not route_exists(url, routes):
            route_template_problems.append(f"{url}: missing route")
        elif not (root / "templates" / template).exists():
            route_template_problems.append(f"{url}: missing {template}")
        elif template not in rendered:
            # redirect-only routes can be absent here; expected route templates should render directly.
            route_template_problems.append(f"{url}: {template} not referenced by render_template")
    if route_template_problems:
        items.append(RegressionItem("routes.templates", "Route/template wiring", "fail", "; ".join(route_template_problems[:12]), "routes", "Check app.py render_template calls and template file names."))
    else:
        items.append(RegressionItem("routes.templates", "Route/template wiring", "ok", f"{len(EXPECTED_ROUTE_TEMPLATES)} page routes render expected templates", "routes"))

    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_template_context_regressions(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[RegressionItem] = []
    ctx_map = _render_context_map(root)
    problems = []
    for template, expected in EXPECTED_TEMPLATE_CONTEXTS.items():
        supplied_sets = ctx_map.get(template, [])
        if not supplied_sets:
            problems.append(f"{template}: no render_template context found")
            continue
        # OK if any render path supplies the required keys. Some templates may have multiple routes.
        if not any(expected.issubset(keys) for keys in supplied_sets):
            all_keys = sorted(set().union(*supplied_sets)) if supplied_sets else []
            missing = sorted(expected - set(all_keys))
            problems.append(f"{template}: missing {', '.join(missing)}")
    if problems:
        items.append(RegressionItem("templates.context", "High-risk template context keys", "fail", "; ".join(problems[:12]), "templates", "Ensure route handlers pass the variables used by the template."))
    else:
        items.append(RegressionItem("templates.context", "High-risk template context keys", "ok", f"{len(EXPECTED_TEMPLATE_CONTEXTS)} high-risk templates have expected route context", "templates"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items), "contexts": {k: [sorted(x) for x in v] for k, v in ctx_map.items()}}


def _scenario_configs(base: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {"current_example": copy.deepcopy(base)}

    missing_policies = copy.deepcopy(base)
    missing_policies.pop("policies", None)
    scenarios["missing_policies"] = missing_policies

    legacy_ppoe = copy.deepcopy(base)
    stale = legacy_ppoe.setdefault("policies", {}).setdefault("stale_lifecycle", {}).setdefault("sources", {})
    pppoe = stale.pop("pppoe", None)
    stale["ppoe"] = pppoe or {"identity": "username"}
    scenarios["legacy_ppoe_alias"] = legacy_ppoe

    missing_setup = copy.deepcopy(base)
    missing_setup.pop("setup_wizard", None)
    missing_setup.pop("notifications", None)
    missing_setup.pop("package_quality", None)
    scenarios["missing_setup_notifications_package_quality"] = missing_setup

    old_schema = copy.deepcopy(base)
    old_schema["config_schema_version"] = 1
    old_schema.get("policies", {}).pop("auto_apply_policy", None)
    old_schema.get("policies", {}).pop("stale_lifecycle", None)
    scenarios["old_schema_missing_v250_keys"] = old_schema

    return scenarios


def check_config_migration_regressions(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[RegressionItem] = []
    from engine.config_schema import migrate_config_schema, validate_schema

    try:
        base = _load_example_config(root)
    except Exception as exc:
        item = RegressionItem("config.example.load", "Load config.json.example", "fail", str(exc), "config", "Fix config.json.example JSON.")
        return {"items": [item.to_dict()], "summary": _summary([item])}

    failures = []
    warnings = []
    for name, cfg in _scenario_configs(base).items():
        migrated, notes = migrate_config_schema(cfg)
        report = validate_schema(migrated)
        errs = report.get("errors") or []
        warns = report.get("warnings") or []
        missing_policy = [w for w in warns if str(w).startswith("Missing policy setting:")]
        if errs or missing_policy:
            failures.append(f"{name}: errors={errs[:3]} missing={missing_policy[:5]}")
        elif warns:
            warnings.append(f"{name}: {warns[:3]}")
        # Required modern blocks that caused upgrade/fresh-install regressions.
        required_paths = [
            ("policies", "stale_lifecycle", "sources", "pppoe"),
            ("policies", "auto_apply_policy"),
            ("setup_wizard",),
            ("notifications", "telegram"),
            ("package_quality",),
        ]
        for path in required_paths:
            cur: Any = migrated
            ok = True
            for part in path:
                if not isinstance(cur, dict) or part not in cur:
                    ok = False
                    break
                cur = cur[part]
            if not ok:
                failures.append(f"{name}: missing {'.'.join(path)} after migration")
    if failures:
        items.append(RegressionItem("config.migration", "Config migration scenarios", "fail", "; ".join(failures[:10]), "config", "Update schema migration/default merge logic."))
    else:
        detail = f"{len(_scenario_configs(base))} scenario configs migrate without schema errors or missing policy warnings"
        if warnings:
            detail += f"; warnings: {'; '.join(warnings[:3])}"
        items.append(RegressionItem("config.migration", "Config migration scenarios", "ok", detail, "config"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def _base_policy_config() -> dict[str, Any]:
    from engine.policy_defaults import smart_policy_defaults
    return {
        "app": {"auto_apply": True, "backup_before_apply": True},
        "policies": smart_policy_defaults(),
        "routers": [
            {
                "name": "R1",
                "enabled": True,
                "pppoe": {"enabled": True},
                "dhcp": {"enabled": True, "servers": [{"name": "LAN", "enabled": True}]},
                "hotspot": {"enabled": True},
            }
        ],
    }


def check_policy_behavior_regressions(root: str | Path) -> dict[str, Any]:
    _ = Path(root)
    items: list[RegressionItem] = []
    failures = []
    try:
        from engine.policy_engine import evaluate_cleanup_policy, evaluate_apply_guards, evaluate_auto_apply_policy, PolicyDecision

        cfg = _base_policy_config()
        # DHCP normal inactive is intentionally immediate by default.
        dec = evaluate_cleanup_policy(cfg, {}, [{"code": "DHCP-a", "source": "DHCP"}], {"DHCP"}, {"DHCP": 1}, {"DHCP": 3})
        if "DHCP-a" not in dec.remove_codes or dec.verdict != "safe_to_apply":
            failures.append("DHCP normal inactive should cleanup immediately by default")

        # PPP source disabled must require confirmation, not silent deletion.
        cfg2 = _base_policy_config()
        cfg2["routers"][0]["pppoe"]["enabled"] = False
        dec = evaluate_cleanup_policy(cfg2, {}, [{"code": "PPP-user1", "source": "PPP"}], set(), {"PPP": 0}, {"PPP": 10})
        if not dec.requires_confirmation or "PPP-user1" not in dec.preserve_codes:
            failures.append("PPPoE disabled should require confirmation and preserve rows")

        # Collector failed should preserve rows by default.
        cfg3 = _base_policy_config()
        dec = evaluate_cleanup_policy(cfg3, {}, [{"code": "PPP-user2", "source": "PPP"}], set(), {"PPP": 0}, {"PPP": 10})
        if "PPP-user2" not in dec.preserve_codes or dec.remove_codes:
            failures.append("Collector failure should preserve rows and avoid removal")

        # Zero result should block cleanup for DHCP by default.
        dec = evaluate_cleanup_policy(cfg3, {"last_successful_source_counts": {"DHCP": 42}}, [{"code": "DHCP-zero", "source": "DHCP"}], {"DHCP"}, {"DHCP": 0}, {"DHCP": 42})
        if "DHCP-zero" not in dec.preserve_codes or not dec.warnings:
            failures.append("DHCP zero-result should preserve/block cleanup by default")

        # Duplicate IP/missing parent/collector failure preflight blocks apply when guards enabled.
        guard_dec = evaluate_apply_guards(cfg3, PolicyDecision(), {"errors": ["duplicate IP found"], "warnings": []}, type("R", (), {"router_errors": []})())
        if guard_dec.apply_allowed or guard_dec.write_allowed:
            failures.append("Duplicate IP preflight should block apply/write")

        # Risk-aware auto-apply allows low risk but holds high risk.
        low = PolicyDecision().finalize()
        allowed, _, _details = evaluate_auto_apply_policy(cfg3, low, True, "files_changed")
        if not allowed:
            failures.append("Low risk auto-apply should be allowed by default")
        high = PolicyDecision(risk_score=90).finalize()
        allowed, reason, _details = evaluate_auto_apply_policy(cfg3, high, True, "files_changed")
        if allowed or "held" not in reason:
            failures.append("High/critical risk auto-apply should be held by default")
    except Exception as exc:
        failures.append(f"policy behavior test crashed: {exc}")

    if failures:
        items.append(RegressionItem("policy.behavior", "Policy safety behavior", "fail", "; ".join(failures), "policy", "Review policy_engine defaults and guard logic."))
    else:
        items.append(RegressionItem("policy.behavior", "Policy safety behavior", "ok", "Cleanup, apply-guard, and auto-apply safety cases pass", "policy"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_operations_center_regressions(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[RegressionItem] = []
    routes = collect_app_routes(root)
    templates = root / "templates"
    ops = templates / "operations.html"
    problems = []
    for url in ("/operations", "/services", "/logs"):
        if not route_exists(url, routes):
            problems.append(f"missing {url}")
    if not ops.exists():
        problems.append("missing templates/operations.html")
    else:
        text = ops.read_text(encoding="utf-8", errors="ignore")
        for needle in ("apply_pagination", "audit_pagination", "backup_pagination", "journal_lines_count", "active_tab"):
            if needle not in text:
                problems.append(f"operations.html missing {needle}")
        if "{{ '\\n'.join(lines) }}" not in text and "join(lines)" not in text:
            problems.append("operations.html app log viewer no longer joins app log lines")
    if problems:
        items.append(RegressionItem("operations.wiring", "Operations Center compatibility", "fail", "; ".join(problems), "operations", "Restore Operations Center route/template pagination variables."))
    else:
        items.append(RegressionItem("operations.wiring", "Operations Center compatibility", "ok", "Operations, services/logs redirects, and pagination variables are present", "operations"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_documentation_regressions(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[RegressionItem] = []
    failures = []
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        version = ""
        failures.append("VERSION missing")
    for rel in ("README.md", "FULL_DOCUMENTATION.md", "RELEASE_NOTES.md", "docs/docs_manifest.json", "docs/DOCUMENTATION_INDEX.md"):
        if not (root / rel).exists():
            failures.append(f"missing {rel}")
    try:
        manifest = json.loads((root / "docs" / "docs_manifest.json").read_text(encoding="utf-8"))
        entries = manifest.get("entries", manifest if isinstance(manifest, list) else [])
        missing_docs = []
        for entry in entries if isinstance(entries, list) else []:
            path = entry.get("path") or entry.get("file") or entry.get("source")
            if path and not (root / path).exists():
                missing_docs.append(path)
        if missing_docs:
            failures.append("docs_manifest missing files: " + ", ".join(missing_docs[:10]))
    except Exception as exc:
        failures.append(f"docs_manifest invalid: {exc}")
    if version:
        release = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8", errors="ignore") if (root / "RELEASE_NOTES.md").exists() else ""
        if version not in release:
            failures.append(f"release notes do not mention VERSION {version}")
    if failures:
        items.append(RegressionItem("docs.integrity", "Documentation integrity", "fail", "; ".join(failures), "docs", "Update docs manifest, release notes, and GitHub docs."))
    else:
        items.append(RegressionItem("docs.integrity", "Documentation integrity", "ok", "Docs manifest, GitHub docs, and release notes are internally consistent", "docs"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def compute_regression_suite(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    from engine.policy_path_audit import audit_policy_and_paths
    from engine.ui_wiring_audit import audit_ui_wiring
    sections = {
        "routes": check_route_regressions(root),
        "templates": check_template_context_regressions(root),
        "config_migration": check_config_migration_regressions(root),
        "policy_behavior": check_policy_behavior_regressions(root),
        "policy_path_audit": audit_policy_and_paths(root),
        "ui_wiring": audit_ui_wiring(root),
        "operations": check_operations_center_regressions(root),
        "documentation": check_documentation_regressions(root),
    }
    items = []
    for section in sections.values():
        items.extend(section.get("items", []))
    summary = {
        "ok": sum(1 for i in items if i["status"] == "ok"),
        "warn": sum(1 for i in items if i["status"] == "warn"),
        "fail": sum(1 for i in items if i["status"] == "fail"),
    }
    verdict = "pass" if summary["fail"] == 0 else "fail"
    if verdict == "pass" and summary["warn"]:
        verdict = "pass_with_warnings"
    return {"verdict": verdict, "summary": summary, "items": items, "sections": sections}
