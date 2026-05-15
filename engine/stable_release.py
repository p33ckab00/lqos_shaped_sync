"""Stable Release Candidate checks for LQoSync.

v2.70 is a feature-freeze / production-stabilization release. These helpers are
read-only and classify routes, compatibility aliases, deprecated templates, and
pre/post-update checks so operators can validate a release without adding more UI
surface area.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from engine.release_integrity import collect_app_routes, collect_render_templates, collect_internal_links, route_exists, compute_release_integrity
from engine.regression import compute_regression_suite, check_config_migration_regressions
from engine.policy_path_audit import audit_policy_and_paths

STABLE_RELEASE_TARGET = "v2.70 Stable Release Candidate"
FEATURE_FREEZE_POLICY = {
    "status": "active",
    "allowed": [
        "bug fixes",
        "route cleanup",
        "UI consistency fixes",
        "docs cleanup",
        "installer/update safety",
        "config migration safety",
        "test coverage",
    ],
    "not_allowed": [
        "new sidebar modules",
        "experimental engines",
        "new production behavior without tests",
        "duplicated configuration pages",
    ],
}

ROUTE_COMPATIBILITY = [
    {"old": "/health", "destination": "/", "status": "compatibility_redirect", "purpose": "Dashboard owns live health/status."},
    {"old": "/services", "destination": "/operations?tab=services", "status": "compatibility_redirect", "purpose": "Operations Center owns services/journals."},
    {"old": "/logs", "destination": "/operations?tab=logs", "status": "compatibility_redirect", "purpose": "Operations Center owns logs/backups/audit."},
    {"old": "/policy", "destination": "/config?tab=policies", "status": "compatibility_redirect", "purpose": "Config Center owns policy settings."},
    {"old": "/notifications", "destination": "/config?tab=notifications", "status": "compatibility_redirect", "purpose": "Config Center owns notification delivery settings."},
    {"old": "/routers", "destination": "/config?tab=routers", "status": "compatibility_redirect", "purpose": "Router Insight lives beside router settings to avoid duplicate UX."},
]

ACTIVE_PAGE_TEMPLATES = {
    "base.html",
    "dashboard.html",
    "config.html",
    "operations.html",
    "reports.html",
    "lifecycle.html",
    "network_layout.html",
    "shaped_devices.html",
    "dry_run.html",
    "setup_wizard.html",
    "setup_repair.html",
    "updates.html",
    "docs_search.html",
    "docs_view.html",
    "settings_users.html",
    "about.html",
    "backup_preview.html",
    "login.html",
    "dashboard_health_performance_fragment.html",
    "dashboard_lifecycle_fragment.html",
    "dashboard_policy_decision_fragment.html",
    "dashboard_production_readiness_fragment.html",
    "dashboard_smart_insights_fragment.html",
    "dry_run_policy_verdict_fragment.html",
    "dry_run_smart_insights_fragment.html",
}

COMPATIBILITY_TEMPLATES = {
    "health.html": "Compatibility/deprecated health page; Dashboard is live health owner.",
    "services.html": "Compatibility/deprecated services page; Operations Center is services/journals owner.",
    "logs.html": "Compatibility/deprecated logs page; Operations Center is logs/backups owner.",
    "policy_center.html": "Compatibility/deprecated policy page; Config Center policies tab is canonical.",
    "notifications.html": "Compatibility/deprecated notification page; Config Center notifications tab is canonical.",
}


@dataclass
class StableItem:
    key: str
    title: str
    status: str  # ok | warn | fail
    detail: str
    category: str = "stable"
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _summary(items: list[StableItem]) -> dict[str, int]:
    return {"ok": sum(i.status == "ok" for i in items), "warn": sum(i.status == "warn" for i in items), "fail": sum(i.status == "fail" for i in items)}


def route_compatibility_report(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    routes = collect_app_routes(root)
    rows = []
    missing = []
    for item in ROUTE_COMPATIBILITY:
        exists = route_exists(item["old"], routes)
        row = {**item, "exists": exists}
        rows.append(row)
        if not exists:
            missing.append(item["old"])
    return {"routes": rows, "missing": missing, "ok": not missing}


def template_classification(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    template_dir = root / "templates"
    files = sorted(p.name for p in template_dir.glob("*.html")) if template_dir.exists() else []
    rendered = set(collect_render_templates(root))
    rows = []
    for name in files:
        if name in ACTIVE_PAGE_TEMPLATES:
            status = "active"
            note = "Active canonical page or fragment."
        elif name in COMPATIBILITY_TEMPLATES:
            status = "compatibility_or_deprecated"
            note = COMPATIBILITY_TEMPLATES[name]
        elif name in rendered:
            status = "active_fragment_or_secondary"
            note = "Referenced by render_template or include path."
        else:
            status = "review"
            note = "Not classified as active or compatibility; review before stable tag."
        rows.append({"template": name, "status": status, "note": note})
    review = [r for r in rows if r["status"] == "review"]
    return {"templates": rows, "review": review, "ok": not review}


def update_preflight_check(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    checks = []
    # Keep this local/read-only; scripts can run the individual commands for details.
    for rel, title in [
        ("VERSION", "VERSION file"),
        ("config.json.example", "Config example"),
        ("scripts/release_check.py", "Release check script"),
        ("scripts/regression_check.py", "Regression check script"),
        ("scripts/config_migration_check.py", "Config migration check script"),
        ("scripts/policy_path_audit.py", "Policy/path audit script"),
        ("scripts/lqosync-doctor.sh", "Doctor wrapper"),
    ]:
        p = root / rel
        checks.append({"key": rel, "title": title, "ok": p.exists(), "detail": "present" if p.exists() else "missing"})
    try:
        json.loads((root / "config.json.example").read_text(encoding="utf-8"))
        checks.append({"key": "config.example.json", "title": "Config example JSON", "ok": True, "detail": "parses"})
    except Exception as exc:
        checks.append({"key": "config.example.json", "title": "Config example JSON", "ok": False, "detail": str(exc)})
    return {"checks": checks, "ok": all(c["ok"] for c in checks)}


def compute_stable_release_check(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    items: list[StableItem] = []

    compat = route_compatibility_report(root)
    if compat["ok"]:
        items.append(StableItem("routes.compatibility", "Route compatibility map", "ok", f"{len(compat['routes'])} compatibility aliases are present", "routes"))
    else:
        items.append(StableItem("routes.compatibility", "Route compatibility map", "fail", "Missing aliases: " + ", ".join(compat["missing"]), "routes", "Restore compatibility redirects before stable release."))

    templates = template_classification(root)
    if templates["ok"]:
        items.append(StableItem("templates.classification", "Template classification", "ok", f"{len(templates['templates'])} templates classified as active/compatibility/secondary", "templates"))
    else:
        names = ", ".join(r["template"] for r in templates["review"][:10])
        items.append(StableItem("templates.classification", "Template classification", "warn", f"Templates need review: {names}", "templates", "Run python3 scripts/cleanup_stale_files.py --apply, then rerun scripts/stable_release_check.py."))

    preflight = update_preflight_check(root)
    if preflight["ok"]:
        items.append(StableItem("update.preflight", "Update preflight files", "ok", f"{len(preflight['checks'])} required release/update files are present", "update"))
    else:
        bad = ", ".join(c["key"] for c in preflight["checks"] if not c["ok"])
        items.append(StableItem("update.preflight", "Update preflight files", "fail", f"Missing/bad: {bad}", "update", "Restore missing scripts/config docs before release."))

    release = compute_release_integrity(root)
    if release["summary"].get("fail"):
        items.append(StableItem("release.integrity", "Release integrity", "fail", f"FAIL={release['summary'].get('fail')} WARN={release['summary'].get('warn')}", "release", "Run scripts/release_check.py and fix failures."))
    elif release["summary"].get("warn"):
        items.append(StableItem("release.integrity", "Release integrity", "warn", f"WARN={release['summary'].get('warn')}", "release", "Review warnings before stable tag."))
    else:
        items.append(StableItem("release.integrity", "Release integrity", "ok", f"OK={release['summary'].get('ok')}", "release"))

    regression = compute_regression_suite(root)
    if regression["summary"].get("fail"):
        items.append(StableItem("regression.suite", "Regression suite", "fail", f"FAIL={regression['summary'].get('fail')} WARN={regression['summary'].get('warn')}", "regression", "Run scripts/regression_check.py and fix failures."))
    elif regression["summary"].get("warn"):
        items.append(StableItem("regression.suite", "Regression suite", "warn", f"WARN={regression['summary'].get('warn')}", "regression", "Review warnings before stable tag."))
    else:
        items.append(StableItem("regression.suite", "Regression suite", "ok", f"OK={regression['summary'].get('ok')}", "regression"))

    migration = check_config_migration_regressions(root)
    if migration["summary"].get("fail"):
        items.append(StableItem("config.migration", "Config migration", "fail", f"FAIL={migration['summary'].get('fail')}", "config", "Run scripts/config_migration_check.py and fix migration gaps."))
    else:
        items.append(StableItem("config.migration", "Config migration", "ok", f"OK={migration['summary'].get('ok')}", "config"))

    policy_paths = audit_policy_and_paths(root)
    if policy_paths["summary"].get("fail"):
        items.append(StableItem("policy.path_audit", "Policy/path audit", "fail", f"FAIL={policy_paths['summary'].get('fail')} WARN={policy_paths['summary'].get('warn')}", "policy", "Run scripts/policy_path_audit.py and fix missing paths/policies."))
    elif policy_paths["summary"].get("warn"):
        items.append(StableItem("policy.path_audit", "Policy/path audit", "warn", f"WARN={policy_paths['summary'].get('warn')}", "policy", "Review warnings before stable tag."))
    else:
        items.append(StableItem("policy.path_audit", "Policy/path audit", "ok", f"OK={policy_paths['summary'].get('ok')}", "policy"))

    version = (root / "VERSION").read_text(encoding="utf-8", errors="ignore").strip() if (root / "VERSION").exists() else "unknown"
    if not version.startswith("2.70"):
        items.append(StableItem("version.rc", "Stable release version", "warn", f"VERSION is {version}; expected 2.70.x for RC", "release", "Update VERSION and release notes before packaging v2.70."))
    else:
        items.append(StableItem("version.rc", "Stable release version", "ok", f"VERSION={version}", "release"))

    summary = _summary(items)
    verdict = "pass" if summary["fail"] == 0 else "fail"
    if verdict == "pass" and summary["warn"]:
        verdict = "pass_with_warnings"
    return {
        "target": STABLE_RELEASE_TARGET,
        "feature_freeze": FEATURE_FREEZE_POLICY,
        "verdict": verdict,
        "summary": summary,
        "items": [i.to_dict() for i in items],
        "route_compatibility": compat,
        "template_classification": templates,
        "update_preflight": preflight,
    }
