"""Package quality, route/template integrity, and default repair helpers.

v2.55 adds release-integrity checks so LQoSync can detect packaging gaps such as
navigation links pointing at missing routes, routes rendering missing templates,
or config defaults that no longer satisfy the current schema.

The checks are intentionally read-only unless ``repair_config_defaults`` is
called explicitly by the WebUI or operator scripts.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

@dataclass
class IntegrityItem:
    key: str
    title: str
    status: str  # ok | warn | fail
    detail: str
    category: str = "release"
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status(items: list[IntegrityItem]) -> dict[str, int]:
    return {
        "ok": sum(1 for i in items if i.status == "ok"),
        "warn": sum(1 for i in items if i.status == "warn"),
        "fail": sum(1 for i in items if i.status == "fail"),
    }


def _iter_template_files(root: Path):
    tdir = root / "templates"
    if not tdir.exists():
        return []
    return sorted(tdir.glob("*.html"))


def _route_to_regex(route: str) -> re.Pattern:
    # Flask converters: /reports/export/<fmt>, /users/<path:username>
    marker = "__LQOSYNC_ROUTE_VAR__"
    normalized = re.sub(r"<[^>]+>", marker, route)
    escaped = re.escape(normalized).replace(re.escape(marker), r"[^/]+")
    return re.compile("^" + escaped + "$")


def collect_app_routes(root: str | Path) -> list[str]:
    """Return static Flask route patterns found in app.py."""
    root = Path(root)
    app_py = root / "app.py"
    if not app_py.exists():
        return []
    tree = ast.parse(app_py.read_text(encoding="utf-8"), filename=str(app_py))
    routes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if isinstance(func, ast.Attribute) and func.attr == "route" and dec.args:
                arg = dec.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    routes.append(arg.value)
    return sorted(set(routes))


def collect_render_templates(root: str | Path) -> list[str]:
    root = Path(root)
    app_py = root / "app.py"
    if not app_py.exists():
        return []
    text = app_py.read_text(encoding="utf-8")
    found = re.findall(r"render_template\(\s*['\"]([^'\"]+)['\"]", text)
    return sorted(set(found))


def collect_internal_links(root: str | Path) -> list[dict[str, str]]:
    """Collect static internal href/action URLs from templates.

    Dynamic Jinja-generated URLs are ignored. Query strings and fragments are
    stripped. Static file links are ignored.
    """
    root = Path(root)
    links: list[dict[str, str]] = []
    pattern = re.compile(r"\b(?:href|action)=['\"](/[^'\"#?]*)")
    for tmpl in _iter_template_files(root):
        text = tmpl.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            url = match.group(1)
            if url.startswith(("/static/", "/favicon", "/apple-touch", "/android-chrome", "/site.webmanifest")):
                continue
            if "{{" in url or "{%" in url:
                continue
            links.append({"template": tmpl.name, "url": url})
    # de-duplicate while preserving source context
    seen = set()
    out = []
    for item in links:
        key = (item["template"], item["url"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def route_exists(url: str, routes: list[str]) -> bool:
    if url in routes:
        return True
    return any(_route_to_regex(route).match(url) for route in routes)


def check_route_template_integrity(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[IntegrityItem] = []
    routes = collect_app_routes(root)
    links = collect_internal_links(root)
    rendered_templates = collect_render_templates(root)

    if routes:
        items.append(IntegrityItem("routes.present", "Flask routes discovered", "ok", f"{len(routes)} routes found", "routes"))
    else:
        items.append(IntegrityItem("routes.present", "Flask routes discovered", "fail", "No @app.route decorators found in app.py", "routes", "Check app.py packaging."))

    missing_links = [x for x in links if not route_exists(x["url"], routes)]
    if missing_links:
        detail = "; ".join(f"{x['template']} -> {x['url']}" for x in missing_links[:12])
        items.append(IntegrityItem("routes.nav_links", "Navigation/template links resolve", "fail", detail, "routes", "Add missing app.py routes or remove stale template links."))
    else:
        items.append(IntegrityItem("routes.nav_links", "Navigation/template links resolve", "ok", f"{len(links)} static internal links checked", "routes"))

    missing_templates = [t for t in rendered_templates if not (root / "templates" / t).exists()]
    if missing_templates:
        items.append(IntegrityItem("templates.rendered", "Rendered templates exist", "fail", ", ".join(missing_templates), "templates", "Add missing template files or fix render_template names."))
    else:
        items.append(IntegrityItem("templates.rendered", "Rendered templates exist", "ok", f"{len(rendered_templates)} render_template references checked", "templates"))

    # Check high-value feature route/file combinations that previously regressed.
    feature_checks = [
        ("reports", "/reports", "templates/reports.html", "engine/reports.py"),
        ("router_insight", "/config", "templates/config.html", "engine/router_overview.py"),
        ("lifecycle", "/lifecycle", "templates/lifecycle.html", "engine/lifecycle_report.py"),
        ("policy", "/policy", "templates/policy_center.html", "engine/policy_schema.py"),
        ("setup_repair", "/setup-repair", "templates/setup_repair.html", "engine/setup_repair.py"),
        ("setup_wizard", "/setup-wizard", "templates/setup_wizard.html", "engine/setup_wizard.py"),
    ]
    for key, route, template, engine in feature_checks:
        problems = []
        if not route_exists(route, routes):
            problems.append(f"missing route {route}")
        if not (root / template).exists():
            problems.append(f"missing {template}")
        if not (root / engine).exists():
            problems.append(f"missing {engine}")
        if problems:
            items.append(IntegrityItem(f"feature.{key}", f"{key.replace('_',' ').title()} wiring", "fail", "; ".join(problems), "features"))
        else:
            items.append(IntegrityItem(f"feature.{key}", f"{key.replace('_',' ').title()} wiring", "ok", f"{route}, {template}, and {engine} are present", "features"))

    return {"items": [i.to_dict() for i in items], "summary": _status(items), "routes": routes, "links_checked": links}


def check_config_defaults(root: str | Path) -> dict[str, Any]:
    """Validate config.json.example and policy defaults against current schema."""
    from engine.config_schema import migrate_config_schema, validate_schema
    from engine.policy_schema import POLICY_SCHEMA, get_by_path

    root = Path(root)
    items: list[IntegrityItem] = []
    cfg_path = root / "config.json.example"
    if not cfg_path.exists():
        return {"items": [IntegrityItem("config.example", "config.json.example exists", "fail", "config.json.example missing", "config", "Restore config.json.example").to_dict()], "summary": {"ok": 0, "warn": 0, "fail": 1}}
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        items.append(IntegrityItem("config.example.json", "config.json.example JSON", "ok", "JSON parses successfully", "config"))
    except Exception as exc:
        return {"items": [IntegrityItem("config.example.json", "config.json.example JSON", "fail", str(exc), "config", "Fix invalid JSON.").to_dict()], "summary": {"ok": 0, "warn": 0, "fail": 1}}

    migrated, notes = migrate_config_schema(raw)
    schema = validate_schema(migrated)
    for note in notes:
        items.append(IntegrityItem("config.migration_note", "Config migration note", "info" if False else "warn", note, "config", "Persist config defaults by saving Config Center once or run Smart Defaults Repair."))
    if schema.get("errors"):
        items.append(IntegrityItem("config.schema_errors", "Config schema errors", "fail", "; ".join(schema["errors"][:10]), "config", "Update config.json.example or schema defaults."))
    else:
        items.append(IntegrityItem("config.schema_errors", "Config schema errors", "ok", "No schema errors after migration", "config"))
    warnings = schema.get("warnings") or []
    missing_policy = [w for w in warnings if w.startswith("Missing policy setting:")]
    if missing_policy:
        items.append(IntegrityItem("config.missing_policy", "Policy defaults complete", "fail", "; ".join(missing_policy[:12]), "config", "Add missing paths to policy defaults/schema migration."))
    else:
        items.append(IntegrityItem("config.missing_policy", "Policy defaults complete", "ok", f"{len(POLICY_SCHEMA)} schema policy settings covered", "config"))
    if warnings and not missing_policy:
        items.append(IntegrityItem("config.schema_warnings", "Config schema warnings", "warn", "; ".join(warnings[:10]), "config"))
    elif not warnings:
        items.append(IntegrityItem("config.schema_warnings", "Config schema warnings", "ok", "No warnings after migration", "config"))

    # Ensure canonical PPPoE stale lifecycle key exists.
    pppoe = get_by_path(migrated, "policies.stale_lifecycle.sources.pppoe", None)
    if isinstance(pppoe, dict) and all(k in pppoe for k in ("identity", "grace_enabled", "grace_runs", "return_cancels_cleanup")):
        items.append(IntegrityItem("config.pppoe_stale_lifecycle", "PPPoE stale lifecycle defaults", "ok", "Canonical pppoe stale lifecycle defaults are present", "config"))
    else:
        items.append(IntegrityItem("config.pppoe_stale_lifecycle", "PPPoE stale lifecycle defaults", "fail", "Missing policies.stale_lifecycle.sources.pppoe required keys", "config", "Run Smart Defaults Repair or update policy defaults."))

    try:
        from engine.policy_path_audit import audit_policy_and_paths
        audit = audit_policy_and_paths(root)
        if audit["summary"].get("fail", 0):
            failed = [x for x in audit.get("items", []) if x.get("status") == "fail"]
            detail = "; ".join((x.get("title", "audit") + ": " + x.get("detail", "")) for x in failed[:5])
            items.append(IntegrityItem("config.policy_path_audit", "Policy/path audit", "fail", detail, "config", "Run scripts/policy_path_audit.py and fix missing paths/policies."))
        else:
            items.append(IntegrityItem("config.policy_path_audit", "Policy/path audit", "ok", f"{audit['summary'].get('ok', 0)} policy/path audit checks passed", "config"))
    except Exception as exc:
        items.append(IntegrityItem("config.policy_path_audit", "Policy/path audit", "fail", str(exc), "config", "Fix engine/policy_path_audit.py or policy/default imports."))

    return {"items": [i.to_dict() for i in items], "summary": _status(items), "schema": schema}


def compute_release_integrity(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    route_report = check_route_template_integrity(root)
    config_report = check_config_defaults(root)
    try:
        from engine.ui_wiring_audit import audit_ui_wiring
        ui_report = audit_ui_wiring(root)
        if ui_report["summary"].get("fail", 0):
            failed = [x for x in ui_report.get("items", []) if x.get("status") == "fail"]
            detail = "; ".join((x.get("title", "ui") + ": " + x.get("detail", "")) for x in failed[:5])
            ui_items = [IntegrityItem("ui.wiring", "UI wiring audit", "fail", detail, "ui", "Run scripts/ui_wiring_audit.py and fix role/link/preset/stale wiring gaps.").to_dict()]
        elif ui_report["summary"].get("warn", 0):
            warned = [x for x in ui_report.get("items", []) if x.get("status") == "warn"]
            detail = "; ".join((x.get("title", "ui") + ": " + x.get("detail", "")) for x in warned[:5])
            ui_items = [IntegrityItem("ui.wiring", "UI wiring audit", "warn", detail, "ui", "Review UI wiring warnings before stable tag.").to_dict()]
        else:
            ui_items = [IntegrityItem("ui.wiring", "UI wiring audit", "ok", f"{ui_report['summary'].get('ok', 0)} UI wiring checks passed", "ui").to_dict()]
    except Exception as exc:
        ui_items = [IntegrityItem("ui.wiring", "UI wiring audit", "fail", str(exc), "ui", "Fix engine/ui_wiring_audit.py or template imports.").to_dict()]
    items = [*route_report["items"], *config_report["items"], *ui_items]
    summary = {
        "ok": sum(1 for i in items if i["status"] == "ok"),
        "warn": sum(1 for i in items if i["status"] == "warn"),
        "fail": sum(1 for i in items if i["status"] == "fail"),
    }
    verdict = "pass" if summary["fail"] == 0 else "fail"
    if verdict == "pass" and summary["warn"]:
        verdict = "pass_with_warnings"
    return {
        "verdict": verdict,
        "summary": summary,
        "items": items,
        "route_template": route_report,
        "config_defaults": config_report,
        "ui_wiring": ui_items,
    }


def repair_config_defaults(config_path: str | Path) -> dict[str, Any]:
    """Deep-merge current config with latest defaults and persist it safely."""
    from engine.config_loader import load_config, save_config
    from engine.config_schema import migrate_config_schema, validate_schema

    config_path = Path(config_path)
    before_raw = {}
    if config_path.exists():
        before_raw = json.loads(config_path.read_text(encoding="utf-8"))
    cfg = load_config(str(config_path))
    migrated, notes = migrate_config_schema(cfg)
    save_config(migrated, str(config_path), backup_existing=True)
    after = load_config(str(config_path))
    schema = validate_schema(after)
    return {
        "ok": not schema.get("errors"),
        "config_path": str(config_path),
        "migration_notes": notes,
        "warnings": schema.get("warnings", []),
        "errors": schema.get("errors", []),
        "before_keys": sorted(before_raw.keys()),
        "after_schema_version": after.get("config_schema_version"),
    }
