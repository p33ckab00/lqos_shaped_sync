"""Shared WH/HOW guidance for config.json.

The WebUI Advanced JSON inspector and the install/operator documentation should
tell the same story. This module keeps reusable field-guide rules in one place,
then expands them against the currently loaded config so every visible leaf path
has an answer for What / Why / When / Who / Where / How.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Iterable

from engine.config_metadata import metadata_for_path
from engine.policy_schema import POLICY_SCHEMA


def _rule(
    prefix: str,
    label: str,
    section: str,
    *,
    what: str,
    why: str,
    who: str = "Admin or owner",
    where: str = "Advanced JSON",
    how: str,
    risk: str,
    default: Any = "Varies by deployment",
    example: str = "",
    related_paths: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "prefix": prefix,
        "label": label,
        "section": section,
        "what": what,
        "why": why,
        "who": who,
        "where": where,
        "how": how,
        "risk": risk,
        "default": default,
        "example": example,
        "related_paths": list(related_paths),
    }


CONFIG_GUIDE_RULES: list[dict[str, Any]] = [
    _rule(
        "app.operation_mode",
        "Operation mode",
        "App / live apply",
        what="Chooses whether production flow expects automatic or operator-triggered apply behavior.",
        why="It defines the operating contract for the whole system before scheduler and auto-apply decisions are made.",
        where="Config Center → Policy Center / Overview",
        how="Use automatic only when auto_apply is intentionally enabled and Dry Run is clean; use manual while commissioning or troubleshooting.",
        risk="High if set incorrectly: the system can appear safer or more automated than the operator intends.",
        default="automatic",
        example='"manual" during first commissioning',
        related_paths=("app.auto_apply", "scheduler.enabled"),
    ),
    _rule(
        "app.auto_apply",
        "Auto apply",
        "App / live apply",
        what="Allows future live cycles to apply generated LibreQoS file changes automatically.",
        why="It separates preview-only operation from production automation.",
        where="Config Center → Policy Center / Overview",
        how="Keep disabled until router sources, policies, and Dry Run results are verified. Automatic mode requires this enabled.",
        risk="High: enabling too early can push unintended output into LibreQoS.",
        default=True,
        example="true after successful commissioning",
        related_paths=("app.operation_mode", "policies.auto_apply_policy."),
    ),
    _rule(
        "app.backup_before_apply",
        "Optional auto backup",
        "App / live apply",
        what="Controls whether generated LibreQoS files are backed up before later live applies.",
        why="It trades extra rollback safety for storage growth.",
        where="Config Center → Policy Center / Overview",
        how="Enable when rollback speed matters more than disk usage; if disabled, keep a manual backup habit before major changes.",
        risk="Medium: disabling removes one automatic rollback layer, but remains an allowed operator choice.",
        default=False,
        example="true on high-value production nodes",
        related_paths=("app.backup_retention", "policies.backup_guard."),
    ),
    _rule(
        "app.backup_retention",
        "Backup retention",
        "App / live apply",
        what="Sets how many generated-file backup directories are retained when pruning runs.",
        why="It limits storage growth while preserving rollback history.",
        where="Config Center → Policy Center / Overview",
        how="Increase for slower review cycles; reduce only after confirming backup size and rollback requirements.",
        risk="Medium: a very low value shortens the recovery window.",
        default=10,
        example="10",
        related_paths=("app.backup_before_apply", "paths.backup_dir"),
    ),
    _rule(
        "app.",
        "Application behavior",
        "App / live apply",
        what="Stores system-wide behavior such as application name, default dry-run mode, and file-drift handling.",
        why="These fields describe the operating personality of the service rather than one source or one policy.",
        how="Change only after reading the matching field help; preview output-affecting changes with Dry Run.",
        risk="Varies by field; app.* values can change live-write and apply behavior.",
        related_paths=("scheduler.", "libreqos."),
    ),
    _rule(
        "network_mode",
        "Network layout mode",
        "Network topology",
        what="Defines the high-level hierarchy model used while generating network.json.",
        why="It determines Parent Node semantics, not just a visual preference.",
        where="Config Center → Overview / Network Layout",
        how="Keep the mode that matches the real network hierarchy; review generated network.json and Dry Run after changing it.",
        risk="High: the wrong mode can reshape parent/child topology.",
        default="router_children",
        example='"router_children"',
        related_paths=("flat_network", "no_parent", "routers[].parent_node"),
    ),
    _rule(
        "flat_network",
        "Flat-network compatibility flag",
        "Network topology",
        what="Compatibility flag kept in sync with network_mode for flat layouts.",
        why="Older code/configs still read this flag while network_mode carries the richer intent.",
        how="Do not hand-edit independently; let the Config Center normalize it from network_mode.",
        risk="High when inconsistent with network_mode because generated Parent Node behavior can become misleading.",
        default=False,
        related_paths=("network_mode", "no_parent"),
    ),
    _rule(
        "no_parent",
        "No-parent compatibility flag",
        "Network topology",
        what="Compatibility flag that represents blank Parent Node behavior for flat_no_parent mode.",
        why="It preserves legacy behavior required by generated network.json output.",
        how="Do not hand-edit independently; let the Config Center normalize it from network_mode.",
        risk="High when inconsistent with network_mode because hierarchy output changes.",
        default=False,
        related_paths=("network_mode", "flat_network"),
    ),
    _rule(
        "routers[].password",
        "RouterOS password",
        "Router sources",
        what="Credential used by the read-only RouterOS API client.",
        why="Without it the collector cannot read source data from that router.",
        who="Owner or trusted admin",
        where="Config Center → Selected Router / Advanced JSON",
        how="Use a least-privilege API account, protect config.json permissions, and never share raw screenshots containing secrets.",
        risk="Critical secret: disclosure gives credential material to another actor.",
        default="No universal default",
        related_paths=("routers[].username", "routers[].address", "routers[].port"),
    ),
    _rule(
        "routers[].pppoe.",
        "Router PPPoE source",
        "Router sources",
        what="Defines how one router contributes PPPoE clients and optional PPPoE grouping nodes.",
        why="Source-level settings decide which subscribers become generated rows and how they are grouped.",
        where="Config Center → Selected Router",
        how="Enable only on routers where PPPoE data should feed LibreQoS; use Dry Run after changing node naming or factor rules.",
        risk="High: wrong source or naming settings change generated subscribers and topology.",
        related_paths=("collector.pppoe.", "policies.cleanup_sources.pppoe."),
    ),
    _rule(
        "routers[].dhcp.servers[].",
        "Router DHCP server source",
        "Router sources",
        what="Describes one DHCP server feed, including speed source and generated node naming.",
        why="Different DHCP servers may represent different sites or plans and need separate treatment.",
        where="Config Center → Selected Router",
        how="Name each server exactly as RouterOS reports it, choose the correct plan source, then verify output in Dry Run.",
        risk="High: a wrong server or speed source changes generated client rows.",
        related_paths=("collector.dhcp.", "policies.cleanup_sources.dhcp."),
    ),
    _rule(
        "routers[].dhcp.",
        "Router DHCP source",
        "Router sources",
        what="Enables DHCP collection and holds the configured DHCP server list for one router.",
        why="It is the bridge between router lease data and generated subscriber rows.",
        where="Config Center → Selected Router",
        how="Enable only where leases should be shaped; keep server entries explicit and test discovery before production use.",
        risk="High: wrong enablement can add or remove many dynamic rows.",
        related_paths=("collector.dhcp.", "routers[].dhcp.servers[]."),
    ),
    _rule(
        "routers[].hotspot.",
        "Router Hotspot source",
        "Router sources",
        what="Defines how one router contributes Hotspot sessions/users and generated Hotspot nodes.",
        why="Hotspot identities and session churn differ from subscriber PPPoE behavior.",
        where="Config Center → Selected Router",
        how="Use node names and metadata behavior that match the real Hotspot design; preview before enabling cleanup automation.",
        risk="High: wrong settings can create unstable or misleading generated rows.",
        related_paths=("collector.hotspot.", "policies.cleanup_sources.hotspot."),
    ),
    _rule(
        "routers[].",
        "Router source",
        "Router sources",
        what="Represents one MikroTik router, its root node, credentials, and enabled source types.",
        why="Routers are the primary data sources that feed generated ShapedDevices.csv and network.json.",
        where="Config Center → Routers / Selected Router",
        how="Add one real router at a time, test connectivity, then verify Dry Run output before enabling production automation.",
        risk="High: router edits directly affect collection scope and generated output.",
        related_paths=("collector.", "network_mode"),
    ),
    _rule(
        "collector.",
        "Collector behavior",
        "Collection",
        what="Controls how source data is read from RouterOS.",
        why="Collection quality determines the truth available to builders and policy decisions.",
        where="Config Center → Collectors",
        how="Prefer the least broad successful read mode; change DHCP/Hotspot behavior only when you understand the source data shape.",
        risk="Medium to high: poor collector settings can create false zero results or missing metadata.",
        related_paths=("routers[].", "policies.collector_guard."),
    ),
    _rule(
        "libreqos.",
        "LibreQoS apply runner",
        "Apply engine",
        what="Controls how LQoSync invokes LibreQoS.py after output files change.",
        why="It connects generated files to the actual LibreQoS runtime update.",
        where="Config Center → Apply Policy",
        how="Keep working_dir and run_mode aligned with the install type; use direct mode for bare metal unless deployment docs say otherwise.",
        risk="High: wrong command, working directory, or mode can make applies fail or run in the wrong place.",
        related_paths=("app.auto_apply", "paths."),
    ),
    _rule(
        "scheduler.",
        "Scheduler",
        "Automation",
        what="Controls recurring sync cadence, retry timing, and apply cooldown.",
        why="It decides when the engine wakes up and how aggressively it revisits work.",
        where="Config Center → Scheduler",
        how="Use slower intervals while commissioning; tighten only after collection and apply times are known.",
        risk="Medium: too-fast loops create churn; too-slow loops delay network truth.",
        related_paths=("app.operation_mode", "app.auto_apply"),
    ),
    _rule(
        "defaults.",
        "Generated-row defaults",
        "Generation defaults",
        what="Provides fallback values when source data does not carry a complete plan or row value.",
        why="Builders need deterministic defaults rather than silently emitting incomplete output.",
        where="Config Center → Defaults",
        how="Set defaults to safe business values; watch fallback-speed warnings if they are being used often.",
        risk="Medium: bad defaults can quietly shape many clients at the wrong speed.",
        related_paths=("policies.data_quality.",),
    ),
    _rule(
        "preflight.",
        "Preflight validation",
        "Validation",
        what="Controls validation gates before output write/apply decisions.",
        why="It catches structurally unsafe output before production state changes.",
        where="Config Center → Defaults / Preflight",
        how="Keep blocking behavior for invalid bandwidth or missing parents unless a qualified admin has a specific reason.",
        risk="High when weakened: malformed output can reach production.",
        related_paths=("policies.apply_guard.", "network_mode"),
    ),
    _rule(
        "notifications.telegram.bot_token",
        "Telegram bot token",
        "Notifications",
        what="Secret token used to authenticate outbound Telegram messages.",
        why="Telegram delivery cannot work without bot authentication.",
        who="Owner or trusted admin",
        where="Config Center → Notifications",
        how="Store only the real bot token, keep file permissions tight, and rotate if exposed.",
        risk="Critical secret: disclosure allows message-sending abuse through the bot.",
        default="empty until configured",
        related_paths=("notifications.telegram.chat_id",),
    ),
    _rule(
        "notifications.telegram.",
        "Telegram delivery",
        "Notifications",
        what="Controls outbound Telegram delivery, filtering, dedupe, Safety Alerts, and the Activity Journal.",
        why="It decides which runtime events leave the WebUI, which are urgent, and which become quiet operator-journal entries.",
        where="Config Center → Notifications",
        how="Keep Safety Alerts enabled for urgent conditions, keep Activity Journal digest-first for operational visibility, test once, then tune noise controls.",
        risk="Low to medium except for secret fields; bad settings mostly create silence or alert fatigue.",
        related_paths=("notifications.",),
    ),
    _rule(
        "notifications.telegram.safety_alerts_enabled",
        "Telegram safety alerts",
        "Notifications",
        what="Turns the urgent Telegram lane on or off.",
        why="Policy blocks, confirmation holds, and failed applies need a delivery lane that is hard to miss.",
        where="Config Center → Notifications → Safety Alerts",
        how="Keep enabled in production; tune exact event filters below it rather than disabling the whole lane.",
        risk="Medium: disabling it can hide time-sensitive failures outside the WebUI.",
        default="true",
        related_paths=("notifications.telegram.notify_on_apply_failed", "notifications.telegram.notify_on_policy_block"),
    ),
    _rule(
        "notifications.telegram.activity_journal_enabled",
        "Telegram activity journal",
        "Notifications",
        what="Turns the digest-first operator journal lane on or off.",
        why="Operators often need proof of what changed even when nothing is wrong.",
        where="Config Center → Notifications → Activity Journal",
        how="Keep enabled when you want client-change/apply-success visibility; prefer digest mode for low-noise operation.",
        risk="Low: disabling it removes convenience/history, not safety gates.",
        default="true",
        related_paths=("notifications.telegram.notify_on_client_changes", "notifications.telegram.notify_on_apply_success"),
    ),
    _rule(
        "notifications.telegram.notify_on_client_changes",
        "Telegram client-change journal events",
        "Notifications",
        what="Allows client add/update/remove summaries into the Activity Journal.",
        why="This makes the runtime feed explain what changed in shaped client records after a real cycle.",
        where="Config Center → Notifications → Activity Journal",
        how="Keep enabled if operators should see client movement without opening Audit Logs.",
        risk="Low: can add message volume on busy networks.",
        default="true",
    ),
    _rule(
        "notifications.telegram.notify_on_apply_success",
        "Telegram successful-apply journal events",
        "Notifications",
        what="Allows successful LibreQoS apply confirmations into the Activity Journal.",
        why="A successful file write is not the same as a successful LibreQoS apply; this confirms the final actuation step.",
        where="Config Center → Notifications → Activity Journal",
        how="Keep enabled when operators need positive confirmation that live shaping was applied.",
        risk="Low: visibility-only.",
        default="true",
    ),
    _rule(
        "notifications.",
        "Notification behavior",
        "Notifications",
        what="Controls internal notification surfaces and optional external delivery.",
        why="Operators need timely signals without coupling alert display to every engine decision.",
        where="Config Center → Notifications",
        how="Keep internal center enabled; tune external delivery after verifying real events.",
        risk="Low to medium: mostly affects visibility rather than generation.",
    ),
    _rule(
        "paths.",
        "Filesystem paths",
        "Filesystem",
        what="Maps LQoSync to config, generated files, logs, runtime state, backups, and caches.",
        why="The engine needs exact paths to read truth and write generated artifacts atomically.",
        who="Owner or install admin",
        where="Config Center → Paths / install documentation",
        how="Change only when moving a real file location; verify service-user permissions immediately afterward.",
        risk="Critical: wrong paths can read stale files, fail writes, or update the wrong LibreQoS tree.",
        related_paths=("libreqos.working_dir",),
    ),
    _rule(
        "services.",
        "Service monitoring",
        "Operations",
        what="Defines which systemd units and restart groups appear in Operations Center.",
        why="Installations can have slightly different service names while the UI still needs a reliable map.",
        where="Advanced JSON / Operations Center",
        how="Edit only when the real systemd unit names differ from defaults, then verify Operations Center status.",
        risk="Medium: wrong units make monitoring or restart buttons misleading.",
    ),
    _rule(
        "topology.",
        "Topology editor behavior",
        "Network topology",
        what="Controls advanced topology editing and validation affordances.",
        why="It keeps custom/deep hierarchy features explicit rather than silently available.",
        where="Advanced JSON / Network Layout",
        how="Keep validation enabled; enable advanced topology only when the network model needs it.",
        risk="Medium to high depending on hierarchy complexity.",
        related_paths=("network_mode",),
    ),
    _rule(
        "production_readiness.",
        "Production readiness scoring",
        "Readiness",
        what="Controls Dashboard readiness scoring and optional scheduler blocking behavior.",
        why="It turns many safety signals into one go-live summary.",
        where="Advanced JSON / Dashboard",
        how="Treat scores as guidance; do not weaken checks merely to obtain a green card.",
        risk="Medium: hiding checks can make the UI overstate readiness.",
    ),
    _rule(
        "setup_wizard.",
        "Setup wizard",
        "Onboarding",
        what="Controls first-run onboarding behavior and scheduler-readiness requirements.",
        why="It protects fresh installs from jumping directly into unsafe automation.",
        who="Owner or install admin",
        where="Advanced JSON / Setup Wizard",
        how="Keep first-run protections enabled until commissioning is complete.",
        risk="Medium: bypassing gates can normalize incomplete setup.",
    ),
    _rule(
        "setup_repair.",
        "Setup and repair",
        "Onboarding",
        what="Controls guided diagnostics and safe repair affordances.",
        why="It gives admins recovery tools without making repair actions the default operating path.",
        who="Owner or install admin",
        where="Advanced JSON / Setup & Repair",
        how="Keep repair read-only by default; use write repairs deliberately and with backups.",
        risk="Medium to high when write repair actions are enabled casually.",
    ),
    _rule(
        "ui.",
        "UI preference",
        "WebUI",
        what="Controls presentation defaults such as theme, refresh rate, and advanced-view visibility.",
        why="Presentation should be configurable without changing engine truth.",
        where="Advanced JSON / WebUI",
        how="Use these for operator comfort only; do not treat UI values as engine policy.",
        risk="Low.",
    ),
    _rule(
        "monitoring.",
        "Monitoring behavior",
        "Observability",
        what="Controls health/trend collection and how much operational history is summarized.",
        why="It shapes the signal available to dashboards and recommendations.",
        where="Advanced JSON / Dashboard",
        how="Keep enabled in production; reduce sample sizes only when resource limits require it.",
        risk="Low to medium: disabling reduces visibility.",
    ),
    _rule(
        "insights.",
        "Smart insights",
        "Observability",
        what="Controls explanatory cards and recommendation surfaces.",
        why="It separates explanation from enforcement while helping operators understand engine behavior.",
        where="Advanced JSON / Dashboard",
        how="Keep enabled unless deliberately simplifying a constrained UI deployment.",
        risk="Low: affects explanation, not enforcement.",
    ),
    _rule(
        "config_validation.",
        "Config validation",
        "Validation",
        what="Controls schema validation, config health display, and save-time simulation behavior.",
        why="It protects config.json from structurally unsafe edits.",
        who="Owner or install admin",
        where="Advanced JSON / Config Center",
        how="Keep validation and schema blocking enabled; disable only for a controlled migration window.",
        risk="High if weakened: malformed config can be saved more easily.",
    ),
    _rule(
        "package_quality.",
        "Package quality checks",
        "Release integrity",
        what="Controls optional doctor/audit script locations and release-quality checks.",
        why="It lets installs self-check route wiring, migrations, and stale files.",
        who="Owner or maintainer",
        where="Advanced JSON / Setup & Repair",
        how="Keep enabled unless packaging a deliberately stripped development build.",
        risk="Medium: disabling reduces self-diagnosis.",
    ),
    _rule(
        "stable_release.",
        "Stable-release policy",
        "Release integrity",
        what="Describes release-candidate guardrails such as feature freeze and required checks.",
        why="It keeps stabilization work disciplined before a stable release.",
        who="Owner or maintainer",
        where="Advanced JSON / release documentation",
        how="Change only when the project release policy changes, not for ordinary operations.",
        risk="Low operationally, but high for release discipline.",
    ),
    _rule(
        "access_control.",
        "Access-control summary",
        "Security",
        what="Documents role intent and owner-only route summaries inside config.json.",
        why="It keeps install metadata aligned with the role model shown to operators.",
        who="Owner or maintainer",
        where="Advanced JSON / user-management docs",
        how="Treat this as descriptive metadata; route decorators remain the real enforcement layer.",
        risk="Low runtime risk, but stale descriptions mislead operators.",
    ),
    _rule(
        "preserve_network_config",
        "Preserve network config",
        "Network topology",
        what="Compatibility behavior that preserves existing network topology instead of regenerating it in selected flows.",
        why="Some deployments intentionally manage network.json outside the normal generated path.",
        where="Advanced JSON",
        how="Use only when the operator has a deliberate external network.json workflow.",
        risk="High if misunderstood: generated topology may not follow current source data.",
        default=False,
        related_paths=("network_mode", "paths.network_json"),
    ),
]


DEFAULT_GUIDE = _rule(
    "",
    "Config setting",
    "General",
    what="Stored setting read from config.json.",
    why="config.json is the source of truth for runtime readers.",
    how="Change deliberately, save through Config Center when possible, and verify the next relevant cycle or page render.",
    risk="Varies by field. If unsure, search the docs before changing it.",
)


def normalize_config_path(path: str) -> str:
    """Convert concrete list indices into reusable guide paths."""
    return re.sub(r"\[\d+\]", "[]", str(path or ""))


def _policy_guides() -> dict[str, dict[str, Any]]:
    guides: dict[str, dict[str, Any]] = {}
    for item in POLICY_SCHEMA:
        path = str(item.get("path") or "")
        if not path:
            continue
        guides[path] = {
            "prefix": path,
            "label": item.get("label") or path,
            "section": f"Policy / {item.get('section') or 'Policy'}",
            "what": item.get("description") or "Policy setting.",
            "why": "Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.",
            "who": "Admin or owner",
            "where": "Config Center → Policy Center / Advanced JSON",
            "how": item.get("setup_guidance") or "Use the recommended value unless the network needs different behavior.",
            "risk": item.get("risk_note") or f"Risk level: {item.get('risk') or 'varies'}.",
            "default": item.get("recommended"),
            "example": "",
            "related_paths": [],
        }
    return guides


POLICY_GUIDES = _policy_guides()


def _matching_rule(path: str) -> dict[str, Any]:
    normalized = normalize_config_path(path)
    if normalized in POLICY_GUIDES:
        return deepcopy(POLICY_GUIDES[normalized])
    matches = [
        rule
        for rule in CONFIG_GUIDE_RULES
        if normalized == rule["prefix"] or normalized.startswith(rule["prefix"])
    ]
    return deepcopy(max(matches, key=lambda item: len(item["prefix"]))) if matches else deepcopy(DEFAULT_GUIDE)


def guide_for_path(path: str) -> dict[str, Any]:
    """Return full WH/HOW guide metadata for one concrete config path."""
    normalized = normalize_config_path(path)
    guide = _matching_rule(normalized)
    meta = metadata_for_path(path)
    guide.update(
        {
            "path": path,
            "normalized_path": normalized,
            "when": meta.get("effectivity_label") or "Next config read",
            "effectivity": meta.get("effectivity") or "next_read",
            "effectivity_explanation": meta.get("explanation") or "",
        }
    )
    return guide


def _iter_leaf_paths(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _iter_leaf_paths(value[key], child)
        return
    if isinstance(value, list):
        if not value or all(not isinstance(item, (dict, list)) for item in value):
            if prefix:
                yield prefix
            return
        for idx, item in enumerate(value):
            yield from _iter_leaf_paths(item, f"{prefix}[{idx}]")
        return
    if prefix:
        yield prefix


def build_config_guide(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand guide metadata against the current config leaf paths."""
    return [guide_for_path(path) for path in _iter_leaf_paths(config or {})]


def documented_guide_rules() -> list[dict[str, Any]]:
    """Return reusable guide rules suitable for long-form documentation."""
    policy = [deepcopy(POLICY_GUIDES[path]) for path in sorted(POLICY_GUIDES)]
    custom = [deepcopy(rule) for rule in CONFIG_GUIDE_RULES]
    return sorted(policy + custom, key=lambda row: (row["section"], row["prefix"]))


def _fmt_default(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def render_config_field_guide_markdown() -> str:
    """Render the shared guide registry as install/operator documentation."""
    lines = [
        "# Config Field Guide — WH/HOW Reference",
        "",
        "This is the install/operator guide for `config.json`. The WebUI Advanced JSON inspector uses the same registry, so the documentation and live UI answer the same questions:",
        "",
        "- **What** is this field?",
        "- **Why** does it exist?",
        "- **When** does it become effective?",
        "- **Who** should change it?",
        "- **Where** is it used?",
        "- **How** should it be changed safely?",
        "",
        "For dynamic arrays such as routers and DHCP servers, `[]` means “each item in the list”. The live WebUI expands these guide patterns against the current saved `config.json`, so every concrete leaf path receives a guide entry.",
        "",
    ]
    for rule in documented_guide_rules():
        meta = metadata_for_path(rule["prefix"])
        lines.extend(
            [
                f"## `{rule['prefix'] or '*'}` — {rule['label']}",
                "",
                f"- **Section:** {rule['section']}",
                f"- **What:** {rule['what']}",
                f"- **Why:** {rule['why']}",
                f"- **When effective:** {meta.get('effectivity_label', 'Next config read')}. {meta.get('explanation', '')}".rstrip(),
                f"- **Who should change it:** {rule['who']}",
                f"- **Where used:** {rule['where']}",
                f"- **How to use it safely:** {rule['how']}",
                f"- **Default / recommended:** `{_fmt_default(rule['default'])}`",
                f"- **Risk:** {rule['risk']}",
            ]
        )
        if rule.get("example"):
            lines.append(f"- **Example:** `{rule['example']}`")
        if rule.get("related_paths"):
            lines.append("- **Related paths:** " + ", ".join(f"`{p}`" for p in rule["related_paths"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
