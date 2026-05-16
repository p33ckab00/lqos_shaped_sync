"""Canonical config-write pipeline for live config.json updates.

All runtime config writes should pass through this module so normalization,
policy preset reconciliation, revision safety, field-level audit, and future
write behavior stay coherent across Config Center, legacy routes, and setup
flows.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from engine.audit import write_audit
from engine.config_diff import diff_configs
from engine.config_loader import load_config, save_config
from engine.config_metadata import annotate_config_changes
from engine.policy_schema import policy_context_changed, reconcile_policy_mode

NAMED_POLICY_PRESETS = {"conservative", "balanced", "aggressive"}


@dataclass
class ConfigWriteResult:
    config: dict[str, Any]
    previous: dict[str, Any]
    previous_policy_mode: str | None
    policy_mode: str | None
    revision_before: str
    revision: str
    changes: list[dict[str, Any]]
    changed: bool


class ConfigRevisionConflict(RuntimeError):
    """Raised when a stale caller tries to overwrite a newer config revision."""

    def __init__(self, current_config: dict[str, Any], current_revision: str):
        super().__init__("config revision changed")
        self.current_config = current_config
        self.current_revision = current_revision


def config_revision(config: dict[str, Any]) -> str:
    payload = json.dumps(config or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _policy_mode(cfg: dict[str, Any]) -> str | None:
    policies = cfg.get("policies")
    return policies.get("mode") if isinstance(policies, dict) else None


def _prepare(previous: dict[str, Any], proposed: dict[str, Any], *, preserve_requested_policy_mode: bool = False) -> tuple[dict[str, Any], str | None, str | None]:
    previous_mode = _policy_mode(previous)
    prepared = deepcopy(proposed)
    if not preserve_requested_policy_mode and previous_mode in NAMED_POLICY_PRESETS and policy_context_changed(previous, prepared):
        prepared.setdefault("policies", {})["mode"] = "custom"
    prepared = reconcile_policy_mode(prepared)
    return prepared, previous_mode, _policy_mode(prepared)


def _audit_summary(action: str, changes: list[dict[str, Any]]) -> str:
    if not changes:
        return f"{action}: no field changes"
    first = ", ".join(str(c.get("path") or "") for c in changes[:3])
    suffix = f", +{len(changes) - 3} more" if len(changes) > 3 else ""
    return f"{len(changes)} config field(s) changed: {first}{suffix}"


def write_config_snapshot(
    path: str,
    proposed: dict[str, Any],
    *,
    actor: str = "system",
    action: str = "config_saved",
    details: dict[str, Any] | None = None,
    backup_existing: bool = True,
    expected_revision: str | None = None,
    audit_when_unchanged: bool = False,
    preserve_requested_policy_mode: bool = False,
) -> ConfigWriteResult:
    previous = load_config(path)
    revision_before = config_revision(previous)
    if expected_revision and expected_revision != revision_before:
        raise ConfigRevisionConflict(previous, revision_before)

    prepared, previous_mode, policy_mode = _prepare(previous, proposed, preserve_requested_policy_mode=preserve_requested_policy_mode)
    save_config(prepared, path, backup_existing=backup_existing)
    saved = load_config(path)
    revision = config_revision(saved)
    changes = annotate_config_changes(diff_configs(previous, saved, limit=500))
    changed = bool(changes)

    if changed or audit_when_unchanged:
        audit_details = {
            **(details or {}),
            "previous_policy_mode": previous_mode,
            "policy_mode": _policy_mode(saved) or policy_mode,
            "config_revision_before": revision_before,
            "config_revision": revision,
            "change_count": len(changes),
            "changes": changes,
        }
        write_audit(saved, action, actor=actor or "system", details=audit_details, summary=_audit_summary(action, changes))

    return ConfigWriteResult(
        config=saved,
        previous=previous,
        previous_policy_mode=previous_mode,
        policy_mode=_policy_mode(saved) or policy_mode,
        revision_before=revision_before,
        revision=revision,
        changes=changes,
        changed=changed,
    )


def mutate_config(
    path: str,
    mutator: Callable[[dict[str, Any]], None],
    *,
    actor: str = "system",
    action: str = "config_saved",
    details: dict[str, Any] | None = None,
    backup_existing: bool = True,
    audit_when_unchanged: bool = False,
    preserve_requested_policy_mode: bool = False,
) -> ConfigWriteResult:
    current = load_config(path)
    proposed = deepcopy(current)
    mutator(proposed)
    return write_config_snapshot(
        path,
        proposed,
        actor=actor,
        action=action,
        details=details,
        backup_existing=backup_existing,
        expected_revision=config_revision(current),
        audit_when_unchanged=audit_when_unchanged,
        preserve_requested_policy_mode=preserve_requested_policy_mode,
    )
