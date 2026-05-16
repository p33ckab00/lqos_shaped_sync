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
    if "def policy_apply_preset" not in app or "_write_config(" not in app or 'action="policy_preset_applied"' not in app:
        problems.append("policy preset route does not clearly save new config through the canonical writer")
    for preset in ("conservative", "balanced", "aggressive"):
        if f"applyPolicyPreset('{preset}')" not in config:
            problems.append(f"Config Center missing {preset} preset button")
        if f"policyPresetClass('{preset}')" not in config:
            problems.append(f"Config Center missing dynamic active class for {preset} preset button")
    for line in config.splitlines():
        if "applyPolicyPreset(" in line and "btn btn-primary" in line:
            # Hard-coded primary on a preset button recreates the bug where Current=aggressive but Balanced is highlighted.
            problems.append("policy preset buttons contain hard-coded btn-primary instead of cfg.policies.mode-driven active state")
            break
    if "policyPresetActive(preset)" not in config or "policyPresetLabel()" not in config:
        problems.append("Config Center missing preset active/label helpers tied to cfg.policies.mode")
    if "policyIsCustom()" not in config or "customPolicyClass()" not in config or "Customized policies active" not in config:
        problems.append("Config Center missing visible Custom policy state and active custom badge")
    if "/policy/apply-preset/" not in config:
        problems.append("Config Center preset JS is not wired to /policy/apply-preset")
    if "policies.mode" in config and "Preset mode is controlled by the preset buttons" not in config:
        problems.append("policies.mode still looks like a normal editable field")
    if problems:
        items.append(UIWiringItem("policy.preset_wiring", "Policy preset wiring", "fail", "; ".join(problems), "policy", "Wire preset buttons inside Config Center → Policies and keep policies.mode managed."))
    else:
        items.append(UIWiringItem("policy.preset_wiring", "Policy preset wiring", "ok", "Config Center preset buttons, Custom state badge, dynamic active state, backend route, canonical config writer, and managed policies.mode are wired.", "policy"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def check_config_center_state_wiring(root: str | Path) -> dict[str, Any]:
    """Check Config Center dynamic UI state consistency.

    This catches visual-state bugs where an underlying config value is correct
    but the highlighted button/tab/panel does not follow it.
    """
    root = Path(root)
    items: list[UIWiringItem] = []
    config = _read(root, "templates/config.html")
    problems = []

    # Main Config Center tabs: every nav button should have a matching x-show section.
    nav_tabs = set(re.findall(r"@click=\"tab='([^']+)'\"", config))
    section_tabs = set(re.findall(r"x-show=\"tab==='([^']+)'", config))
    missing_sections = sorted(t for t in nav_tabs if t not in section_tabs)
    if missing_sections:
        problems.append("Config nav tabs without matching section: " + ", ".join(missing_sections))

    # Policy tree sections: every tree key should have a matching psec panel.
    tree_match = re.search(r"\{% set tree = \[(.*?)\] %\}", config, re.DOTALL)
    tree_keys = set(re.findall(r"\('([^']+)'\s*,", tree_match.group(1) if tree_match else ""))
    psec_sections = set(re.findall(r"x-show=\"psec==='([^']+)'", config))
    # Policy groups are produced by the policy_group(title, ...) macro, so add those generated psec ids too.
    macro_titles = re.findall(r"policy_group\('([^']+)'", config)
    for title in macro_titles:
        psec_sections.add(title.lower().replace(" ", "_").replace("/", "_"))
    missing_psec = sorted(k for k in tree_keys if k not in psec_sections)
    if missing_psec:
        problems.append("Policy tree items without matching panel: " + ", ".join(missing_psec))

    # Preset active state must follow cfg.policies.mode, not a hard-coded primary button.
    if "policyPresetClass(preset)" not in config or "policyPresetActive(preset)" not in config:
        problems.append("Policy preset active state helpers are missing")
    for line in config.splitlines():
        if "applyPolicyPreset(" in line and "btn btn-primary" in line:
            problems.append("Policy preset button has hard-coded btn-primary instead of dynamic active binding")
            break

    # Policy Overview has policy-adjacent app.* controls. They must mark the
    # policy state as Custom, otherwise operators can change Auto Apply /
    # optional Auto Backup while the UI still says Balanced/Aggressive.
    for needle in (
        'x-model="cfg.app.operation_mode" @change="markPolicyCustom()"',
        'x-model="cfg.app.auto_apply" @change="markPolicyCustom()"',
        'x-model="cfg.app.backup_before_apply" @change="markPolicyCustom()"',
        'x-model.number="cfg.app.backup_retention" @input="markPolicyCustom()"',
    ):
        if needle not in config:
            problems.append("Policy Overview app.* control missing Custom-mode wiring: " + needle)

    # Raw JSON and normal config save must still share one hidden config_json source.
    if 'name="config_json"' not in config or 'x-ref="configJson"' not in config or "syncHidden()" not in config:
        problems.append("Config save form is not clearly wired to the normalized config_json hidden field")

    if problems:
        items.append(UIWiringItem(
            "config.center_state",
            "Config Center UI state wiring",
            "fail",
            "; ".join(problems),
            "config_ui",
            "Keep Config Center nav, policy tree, preset active state, and save form bound to current config state.",
        ))
    else:
        items.append(UIWiringItem("config.center_state", "Config Center UI state wiring", "ok", "Config tabs, policy tree panels, dynamic preset active state, Policy Overview Custom-mode controls, and config save binding are consistent.", "config_ui"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}



def check_checkbox_state_wiring(root: str | Path) -> dict[str, Any]:
    """Check boolean checkbox visual/state binding in Config Center.

    This catches cases where config values are true but the checkbox is not
    visually checked because the dynamic binding is one-way, missing bool
    normalization, or lacks a checked-state visual fallback.
    """
    root = Path(root)
    items: list[UIWiringItem] = []
    config = _read(root, "templates/config.html")
    base = _read(root, "templates/base.html")
    problems = []
    if "asBool(value)" not in config:
        problems.append("Config Center missing asBool() boolean normalizer")
    if 'x-effect="$el.checked = asBool(getPath(' not in config:
        problems.append("Policy boolean checkboxes are not x-effect synchronized to current config values")
    if ':checked="asBool(getPath(' not in config:
        problems.append("Policy boolean checkboxes do not use normalized checked binding")
    if "accent-color:var(--c-accent)" not in config and "accent-color:var(--c-accent)" not in base:
        problems.append("Checkbox checked-state accent color fallback is missing")
    if problems:
        items.append(UIWiringItem(
            "config.checkbox_state",
            "Config checkbox visual state wiring",
            "fail",
            "; ".join(problems),
            "config_ui",
            "Bind boolean policy checkboxes with asBool(getPath(...)), x-effect checked sync, and visible checked-state CSS.",
        ))
    else:
        items.append(UIWiringItem("config.checkbox_state", "Config checkbox visual state wiring", "ok", "Boolean checkboxes use normalized checked binding, x-effect sync, and visible checked-state CSS.", "config_ui"))
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



def check_apply_failure_visibility(root: str | Path) -> dict[str, Any]:
    """Check LibreQoS apply failure notification-to-resolution wiring.

    Apply failures must not be invisible. A notification candidate should point to
    an actionable apply diagnostic page, Operations Center should expose detail
    links, and app.py should provide human/API diagnostic routes.
    """
    root = Path(root)
    items: list[UIWiringItem] = []
    app = _read(root, "app.py")
    health = _read(root, "engine/health_trends.py")
    ops = _read(root, "templates/operations.html")
    dash = _read(root, "templates/dashboard_health_performance_fragment.html")
    diag = _read(root, "engine/apply_diagnostics.py")
    problems = []
    if "def libreqos_apply_detail" not in app or "/libreqos/apply/<run_id>" not in app:
        problems.append("missing human apply diagnostic route")
    if "api_libreqos_apply_diagnostic" not in app:
        problems.append("missing apply diagnostic API route")
    if "get_apply_diagnostic" not in app or not diag:
        problems.append("missing apply diagnostics engine wiring")
    if "/libreqos/apply/{run_id}" not in health or "/operations?tab=apply" not in health:
        problems.append("notification target does not point to apply diagnostic/apply tab")
    if "Detail / Resolve" not in ops or "run.diagnostic.summary" not in ops:
        problems.append("Operations apply history lacks detail/resolve wiring")
    if "Open resolve page" not in dash or "n.target" not in dash:
        problems.append("Dashboard notification cards are not clickable/actionable")
    if problems:
        items.append(UIWiringItem("apply.failure_visibility", "Apply failure visibility wiring", "fail", "; ".join(problems), "apply", "Wire apply health notifications to /libreqos/apply/<run_id>, Operations detail buttons, and dashboard actionable targets."))
    else:
        items.append(UIWiringItem("apply.failure_visibility", "Apply failure visibility wiring", "ok", "LibreQoS apply failures are linked to diagnostic pages, Operations detail buttons, and Dashboard notification targets.", "apply"))
    return {"items": [i.to_dict() for i in items], "summary": _summary(items)}


def audit_ui_wiring(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    sections = {
        "role_visibility": check_role_visibility(root),
        "policy_preset": check_policy_preset_wiring(root),
        "config_center_state": check_config_center_state_wiring(root),
        "checkbox_state": check_checkbox_state_wiring(root),
        "apply_failure_visibility": check_apply_failure_visibility(root),
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
