"""UI wiring audit for LQoSync stable releases.

This read-only audit catches integration gaps that normal route/template checks do
not see: stale role checks after role hardening, actions visible only to literal
admin but hidden from owner, policy preset buttons not wired after moving Policy
Center into Config Center, stale files left by mixed ZIP/Git installs, and
compatibility routes drifting away from canonical compact UI locations.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from engine.release_integrity import collect_app_routes, route_exists


@dataclass
class UIWiringItem:
    key: str
    title: str
    status: str
    detail: str
    category: str = "ui_wiring"
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _summary(items: list[UIWiringItem]) -> dict[str, int]:
    return {
        "ok": sum(1 for i in items if i.status == "ok"),
        "warn": sum(1 for i in items if i.status == "warn"),
        "fail": sum(1 for i in items if i.status == "fail"),
    }


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def _route_function_body(root: Path, route: str) -> str:
    app = root / "app.py"
    if not app.exists():
        return ""
    text = app.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "route" and dec.args:
                arg = dec.args[0]
                if isinstance(arg, ast.Constant) and arg.value == route:
                    return "\n".join(lines[node.lineno - 1: node.end_lineno])
    return ""


def check_role_visibility(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[UIWiringItem] = []
    offender_rows = []
    for tmpl in sorted((root / "templates").glob("*.html")):
        text = tmpl.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            # Exact user.role == 'admin' is unsafe after owner/admin/operator/viewer hardening.
            # Use role_at_least(user.role, 'admin') instead. u.role/user-list display is allowed.
            if "user.role == 'admin'" in line or 'user.role == "admin"' in line:
                offender_rows.append(f"{tmpl.name}:{lineno}")
    if offender_rows:
        items.append(UIWiringItem(
            "role.visibility.literal_admin",
            "Role-hardened action visibility",
            "fail",
            "; ".join(offender_rows[:20]),
            "roles",
            "Replace literal user.role == 'admin' template checks with role_at_least(user.role, 'admin').",
        ))
    else:
        items.append(UIWiringItem("role.visibility.literal_admin", "Role-hardened action visibility", "ok", "No literal user.role == 'admin' checks remain in templates.", "roles"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_policy_preset_wiring(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[UIWiringItem] = []
    app = _read(root, "app.py")
    config = _read(root, "templates/config.html")
    problems = []
    if '@app.route("/policy/apply-preset/<preset>"' not in app:
        problems.append("missing POST /policy/apply-preset/<preset> route")
    if "def policy_apply_preset" not in app or "save_config(new_cfg" not in app:
        problems.append("policy preset route does not clearly save new config")
    for preset in ("conservative", "balanced", "aggressive"):
        if f"applyPolicyPreset('{preset}')" not in config:
            problems.append(f"Config Center missing {preset} preset button")
    if "/policy/apply-preset/" not in config:
        problems.append("Config Center preset JS is not wired to /policy/apply-preset")
    if "policies.mode" in config and "Preset mode is controlled by the preset buttons" not in config:
        problems.append("policies.mode still looks like a normal editable field")
    if problems:
        items.append(UIWiringItem("policy.preset_wiring", "Policy preset wiring", "fail", "; ".join(problems), "policy", "Wire preset buttons inside Config Center → Policies and keep policies.mode managed."))
    else:
        items.append(UIWiringItem("policy.preset_wiring", "Policy preset wiring", "ok", "Config Center preset buttons, backend route, save_config, and managed policies.mode are wired.", "policy"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_compatibility_route_wiring(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    routes = collect_app_routes(root)
    items: list[UIWiringItem] = []
    expected = {
        "/policy": "tab=\"policies\"",
        "/notifications": "tab=\"notifications\"",
        "/routers": "tab=\"routers\"",
        "/services": "operations_center",
        "/logs": "operations_center",
        "/health": "dashboard",
    }
    problems = []
    for route, marker in expected.items():
        if not route_exists(route, routes):
            problems.append(f"missing {route}")
            continue
        body = _route_function_body(root, route)
        if marker not in body and not (route == "/health" and "source-health-performance" in body):
            problems.append(f"{route} does not contain expected redirect marker {marker}")
    if problems:
        items.append(UIWiringItem("routes.compat_canonical", "Compatibility routes point to canonical UI", "fail", "; ".join(problems), "routes", "Keep compatibility routes as redirects into Config Center, Operations Center, or Dashboard."))
    else:
        items.append(UIWiringItem("routes.compat_canonical", "Compatibility routes point to canonical UI", "ok", "Compatibility aliases route to canonical compact UI locations.", "routes"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_stale_files(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[UIWiringItem] = []
    stale = [
        ("templates/routers.html", "Standalone Router page removed; Router Insight lives inside Config Center → Routers."),
        ("app.py.pre_reports_route_fix", "Old one-off app.py backup/debug file should not ship in stable packages."),
    ]
    found = [f"{path}: {reason}" for path, reason in stale if (root / path).exists()]
    if found:
        items.append(UIWiringItem("files.stale", "Stale package files", "warn", "; ".join(found), "files", "Run scripts/cleanup_stale_files.py --apply before packaging or after mixed ZIP/Git installs."))
    else:
        items.append(UIWiringItem("files.stale", "Stale package files", "ok", "No known stale files found.", "files"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_owner_only_links(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items: list[UIWiringItem] = []
    # /updates is owner-only. Static links to it should be role-gated or in owner-only nav/context.
    problems = []
    for tmpl in sorted((root / "templates").glob("*.html")):
        if tmpl.name == "updates.html":
            continue
        text = tmpl.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'href=["\']/updates["\']', text):
            context = text[max(0, m.start() - 180): m.end() + 80]
            if "role_at_least" not in context or "owner" not in context:
                problems.append(f"{tmpl.name}: ungated /updates link")
    if problems:
        items.append(UIWiringItem("links.owner_only", "Owner-only links are gated", "fail", "; ".join(problems), "roles", "Gate /updates links with role_at_least(user.role, 'owner')."))
    else:
        items.append(UIWiringItem("links.owner_only", "Owner-only links are gated", "ok", "Owner-only /updates links are gated by owner role.", "roles"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def audit_ui_wiring(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    sections = {
        "role_visibility": check_role_visibility(root),
        "policy_preset": check_policy_preset_wiring(root),
        "compatibility_routes": check_compatibility_route_wiring(root),
        "owner_links": check_owner_only_links(root),
        "stale_files": check_stale_files(root),
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
