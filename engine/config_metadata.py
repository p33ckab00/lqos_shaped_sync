"""Operator-facing metadata for config paths.

This module keeps effectivity/explanation text in one place so Config Center,
config simulation, and config-write audit events describe the same truth.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONFIG_FIELD_RULES: list[dict[str, str]] = [
    {
        "prefix": "network_mode",
        "label": "Network layout mode",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Controls Parent Node behavior and generated network.json topology.",
    },
    {
        "prefix": "flat_network",
        "label": "Network layout compatibility flag",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Compatibility flag kept consistent with network_mode for flat layout behavior.",
    },
    {
        "prefix": "no_parent",
        "label": "Network layout compatibility flag",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Compatibility flag kept consistent with network_mode for blank Parent Node behavior.",
    },
    {
        "prefix": "routers",
        "label": "Router/source settings",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Changes source collection, generated rows, and router-owned network nodes on the next cycle.",
    },
    {
        "prefix": "policies.",
        "label": "Smart policy",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Changes cleanup, write, and apply decisions; use Dry Run after risky edits.",
    },
    {
        "prefix": "app.auto_apply",
        "label": "Auto apply",
        "effectivity": "next_non_dry_run_cycle",
        "effectivity_label": "Next live cycle",
        "explanation": "Controls whether generated file changes may be applied to LibreQoS automatically.",
    },
    {
        "prefix": "app.operation_mode",
        "label": "Operation mode",
        "effectivity": "next_scheduler_or_manual_action",
        "effectivity_label": "Next scheduler/manual action",
        "explanation": "Changes whether production flow expects automatic or operator-triggered apply behavior.",
    },
    {
        "prefix": "app.backup_before_apply",
        "label": "Auto backup preference",
        "effectivity": "next_live_apply",
        "effectivity_label": "Next live apply",
        "explanation": "Controls whether generated LibreQoS files are backed up before future live applies.",
    },
    {
        "prefix": "app.backup_retention",
        "label": "Backup retention",
        "effectivity": "next_backup_prune",
        "effectivity_label": "Next backup prune",
        "explanation": "Controls how many generated-file backup directories are kept when pruning runs.",
    },
    {
        "prefix": "scheduler.",
        "label": "Scheduler",
        "effectivity": "next_scheduler_loop",
        "effectivity_label": "Next scheduler loop",
        "explanation": "The scheduler rereads config.json before deciding its next run/interval.",
    },
    {
        "prefix": "collector.",
        "label": "Collector behavior",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Changes how MikroTik source data is collected on the next cycle.",
    },
    {
        "prefix": "preflight.",
        "label": "Preflight validation",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Changes validation gates before file write/apply decisions.",
    },
    {
        "prefix": "libreqos.",
        "label": "LibreQoS apply behavior",
        "effectivity": "next_live_apply",
        "effectivity_label": "Next live apply",
        "explanation": "Changes how LibreQoS.py is invoked after generated files are written.",
    },
    {
        "prefix": "defaults.",
        "label": "Generated row defaults",
        "effectivity": "next_sync_cycle",
        "effectivity_label": "Next sync cycle",
        "explanation": "Changes fallback values used while generating future rows/nodes.",
    },
    {
        "prefix": "notifications.telegram.",
        "label": "Telegram delivery",
        "effectivity": "next_notification_dispatch",
        "effectivity_label": "Next notification dispatch",
        "explanation": "Changes Telegram delivery behavior for future notifications.",
    },
    {
        "prefix": "notifications.",
        "label": "Notification behavior",
        "effectivity": "next_notification_dispatch",
        "effectivity_label": "Next notification dispatch",
        "explanation": "Changes future notification generation or delivery behavior.",
    },
    {
        "prefix": "ui.",
        "label": "UI preference",
        "effectivity": "next_page_render",
        "effectivity_label": "Next page render",
        "explanation": "Changes presentation defaults used on later page loads.",
    },
    {
        "prefix": "paths.",
        "label": "Filesystem path",
        "effectivity": "next_use",
        "effectivity_label": "Next use",
        "explanation": "Changes the next read/write that uses this path; verify carefully before live operation.",
    },
    {
        "prefix": "services.",
        "label": "Service monitoring",
        "effectivity": "next_status_refresh",
        "effectivity_label": "Next status refresh",
        "explanation": "Changes future service status/journal lookups in the UI.",
    },
]

DEFAULT_CONFIG_FIELD_META = {
    "prefix": "",
    "label": "Config setting",
    "effectivity": "next_read",
    "effectivity_label": "Next config read",
    "explanation": "config.json is the source of truth; readers use the saved value on their next read.",
}


def metadata_for_path(path: str) -> dict[str, str]:
    text = str(path or "")
    for rule in CONFIG_FIELD_RULES:
        prefix = rule["prefix"]
        if text == prefix or text.startswith(prefix):
            return deepcopy(rule)
    return deepcopy(DEFAULT_CONFIG_FIELD_META)


def annotate_config_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for change in changes or []:
        row = deepcopy(change)
        row["meta"] = metadata_for_path(str(row.get("path") or ""))
        out.append(row)
    return out
