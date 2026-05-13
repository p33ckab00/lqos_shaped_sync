"""Policy-driven safety engine for LQoSync.

The policy engine evaluates proposed cleanup/write/apply decisions before any
files are written or LibreQoS is called. It is intentionally rule-based and
explainable, so the Dashboard and Dry Run can show what happened, why it
matters, and what the operator should do next.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any

from engine.policy_defaults import SMART_POLICY_DEFAULTS, CLEANUP_ACTIONS
from engine.policy_state import (
    cleanup_queue_key,
    cleanup_queue_remove,
    is_confirmation_confirmed,
    queued_cleanup_lookup,
    scope_hash,
    upsert_cleanup_queue,
    upsert_confirmation,
)

SOURCE_KEYS = {"PPP": "pppoe", "DHCP": "dhcp", "HS": "hotspot", "STATIC": "static", "UNKNOWN": "static"}
SOURCE_LABELS = {"PPP": "PPPoE", "DHCP": "DHCP", "HS": "Hotspot", "STATIC": "Static", "UNKNOWN": "Unknown"}


@dataclass
class PolicyDecision:
    verdict: str = "safe_to_apply"
    risk_score: int = 0
    risk_level: str = "low"
    apply_allowed: bool = True
    write_allowed: bool = True
    cleanup_allowed: bool = True
    requires_confirmation: bool = False
    confirmation_items: list[dict[str, Any]] = field(default_factory=list)
    blocked_reasons: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    cleanup_decisions: list[dict[str, Any]] = field(default_factory=list)
    triggered_policies: list[dict[str, Any]] = field(default_factory=list)
    remove_codes: list[str] = field(default_factory=list)
    preserve_codes: list[str] = field(default_factory=list)
    queued_codes: list[str] = field(default_factory=list)

    def add_warning(self, title: str, message: str, severity: str = "warning", **extra):
        self.warnings.append({"title": title, "message": message, "severity": severity, **extra})

    def add_recommendation(self, title: str, reason: str, action: str, severity: str = "info", **extra):
        self.recommendations.append({"title": title, "reason": reason, "action": action, "severity": severity, **extra})

    def add_block(self, title: str, message: str, **extra):
        self.blocked_reasons.append({"title": title, "message": message, "severity": "critical", **extra})
        self.write_allowed = False
        self.apply_allowed = False
        self.cleanup_allowed = False

    def add_policy(self, name: str, result: str, **extra):
        self.triggered_policies.append({"policy": name, "result": result, **extra})

    def finalize(self):
        score = 0
        score += 30 * len(self.blocked_reasons)
        score += 12 * len([w for w in self.warnings if w.get("severity") in {"warning", "high"}])
        score += 20 if self.requires_confirmation else 0
        score += 8 * len([d for d in self.cleanup_decisions if d.get("decision") in {"queued", "preserved", "requires_confirmation"}])
        self.risk_score = min(100, max(self.risk_score, score))
        if self.risk_score >= 81:
            self.risk_level = "critical"
        elif self.risk_score >= 51:
            self.risk_level = "high"
        elif self.risk_score >= 21:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"
        if self.blocked_reasons:
            self.verdict = "blocked_by_policy"
        elif self.requires_confirmation:
            self.verdict = "requires_confirmation"
            self.write_allowed = False
            self.apply_allowed = False
        elif self.risk_level in {"medium", "high"}:
            self.verdict = "apply_with_caution"
        else:
            self.verdict = "safe_to_apply"
        return self

    def to_dict(self):
        return asdict(self)


def _deep_merge(base: dict, override: dict | None) -> dict:
    out = dict(base or {})
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def policies(config: dict) -> dict:
    return _deep_merge(SMART_POLICY_DEFAULTS, config.get("policies") or {})


def action_valid(action: str) -> str:
    return action if action in CLEANUP_ACTIONS else "preserve_rows"


def source_enabled_map(config: dict) -> dict[str, bool]:
    ppp = False
    dhcp = False
    hs = False
    for router in config.get("routers", []) or []:
        if not router.get("enabled", True):
            continue
        ppp = ppp or bool(router.get("pppoe", {}).get("enabled", False))
        dhcp_cfg = router.get("dhcp", {}) or {}
        dhcp = dhcp or bool(dhcp_cfg.get("enabled", False) and any(s.get("enabled", True) for s in dhcp_cfg.get("servers", []) or []))
        hs = hs or bool(router.get("hotspot", {}).get("enabled", False))
    return {"PPP": ppp, "DHCP": dhcp, "HS": hs}


def classify_cleanup_candidates(config: dict, policy_state: dict, candidates: list[dict[str, Any]], source_success: set[str], active_counts: dict[str, int]) -> list[dict[str, Any]]:
    enabled = source_enabled_map(config)
    last_counts = policy_state.get("last_successful_source_counts", {}) or {}
    out = []
    for cand in candidates:
        source = cand.get("source", "UNKNOWN")
        reason = "normal_inactive"
        if source in enabled and not enabled.get(source):
            reason = "source_disabled"
        elif source in enabled and source not in source_success:
            reason = "collector_failed"
        elif source in enabled and enabled.get(source) and source in source_success:
            last = int(last_counts.get(source, 0) or 0)
            now = int(active_counts.get(source, 0) or 0)
            if now == 0 and last > 0:
                reason = "source_zero_result"
        cand = dict(cand)
        cand["reason"] = reason
        out.append(cand)
    return out


def _source_policy(pol: dict, source: str) -> dict:
    key = SOURCE_KEYS.get(source, "static")
    return pol.get("cleanup_sources", {}).get(key, {})


def _action_for_reason(pol: dict, source: str, reason: str) -> str:
    sp = _source_policy(pol, source)
    global_cleanup = pol.get("cleanup", {})
    if reason == "source_disabled":
        return action_valid(sp.get("source_disabled_action") or global_cleanup.get("source_disabled_default_action"))
    if reason == "collector_failed":
        return action_valid(sp.get("collector_failed_action") or global_cleanup.get("collector_failed_default_action"))
    if reason == "source_zero_result":
        return action_valid(sp.get("zero_result_action") or global_cleanup.get("source_zero_result_default_action"))
    if reason == "mass_removal":
        return action_valid(sp.get("mass_removal_action") or pol.get("source_cleanup_guard", {}).get("action"))
    return action_valid(sp.get("normal_inactive_action") or global_cleanup.get("normal_inactive_default_action"))


def _confirmation_id(source: str, reason: str, codes: list[str], apply_mode: str) -> tuple[str, str]:
    sh = scope_hash(codes)
    return f"cleanup-{source.lower()}-{reason}-{apply_mode}-{sh}", sh


def _is_mass_removal(pol: dict, source: str, before_count: int, removed_count: int) -> bool:
    if before_count <= 0 or removed_count <= 0:
        return False
    sp = _source_policy(pol, source)
    if not bool(sp.get("respect_percentage_guards", True)):
        return False
    guard = pol.get("source_cleanup_guard", {}) or {}
    if not guard.get("enabled", True):
        return False
    min_removed = int(guard.get("min_removed_count", 5) or 5)
    threshold = float(guard.get("threshold_percent", 30) or 30)
    percent = (removed_count / before_count) * 100.0
    return removed_count >= min_removed and percent >= threshold


def _small_node_exempt(pol: dict, before_count: int, removed_count: int) -> bool:
    guard = pol.get("small_node_guard", {}) or {}
    if not guard.get("enabled", True):
        return False
    max_node = int(guard.get("max_node_size", 5) or 5)
    return before_count <= max_node and removed_count < before_count


def evaluate_cleanup_policy(config: dict, policy_state: dict, candidates: list[dict[str, Any]], source_success: set[str], active_counts: dict[str, int], existing_source_counts: dict[str, int]) -> PolicyDecision:
    pol = policies(config)
    decision = PolicyDecision()
    if not pol.get("cleanup", {}).get("enabled", True):
        for c in candidates:
            decision.preserve_codes.append(c["code"])
        decision.add_warning("Cleanup disabled", "Cleanup policies are disabled. Existing stale rows are preserved.")
        decision.add_policy("cleanup.enabled", "preserve_rows")
        return decision.finalize()

    candidates = classify_cleanup_candidates(config, policy_state, candidates, source_success, active_counts)
    by_source_reason: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_source_reason[(c.get("source", "UNKNOWN"), c.get("reason", "normal_inactive"))].append(c)

    queued = queued_cleanup_lookup(policy_state)
    confirm_hours = int(pol.get("cleanup", {}).get("confirmation_expires_hours", 24) or 24)

    for (source, reason), group in sorted(by_source_reason.items()):
        codes = [g["code"] for g in group]
        before_count = int(existing_source_counts.get(source, len(group)) or len(group))
        removed_count = len(group)
        effective_reason = reason
        if reason == "normal_inactive" and _is_mass_removal(pol, source, before_count, removed_count):
            effective_reason = "mass_removal"
        if reason == "normal_inactive" and _small_node_exempt(pol, before_count, removed_count):
            # Small-node partial removals should not be blocked by percentage guards.
            effective_reason = "normal_inactive"
        action = _action_for_reason(pol, source, effective_reason)
        label = SOURCE_LABELS.get(source, source)
        title = f"{label} cleanup: {effective_reason.replace('_', ' ')}"

        if action == "cleanup_immediate":
            decision.remove_codes.extend(codes)
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "remove_now", "affected_rows": removed_count})
            decision.add_policy(title, "cleanup_immediate", affected_rows=removed_count)
        elif action == "cleanup_next_run":
            remove_now = []
            queue_now = []
            for code in codes:
                key = cleanup_queue_key(code, source, effective_reason)
                if key in queued:
                    remove_now.append(code)
                else:
                    upsert_cleanup_queue(policy_state, code, source, effective_reason, ttl_hours=confirm_hours)
                    queue_now.append(code)
            if remove_now:
                decision.remove_codes.extend(remove_now)
            if queue_now:
                decision.queued_codes.extend(queue_now)
                decision.preserve_codes.extend(queue_now)
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "queued_or_removed", "queued": len(queue_now), "removed": len(remove_now), "affected_rows": removed_count})
            decision.add_warning(title, f"{len(queue_now)} row(s) queued for next-run cleanup; {len(remove_now)} row(s) already queued and will be removed now.", severity="warning")
        elif action in {"require_confirm_immediate", "require_confirm_next_run"}:
            apply_mode = "immediate" if action.endswith("immediate") else "next_run"
            cid, sh = _confirmation_id(source, effective_reason, codes, apply_mode)
            confirmed = is_confirmation_confirmed(policy_state, cid, sh)
            if confirmed:
                decision.remove_codes.extend(codes)
                decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "confirmed_remove", "affected_rows": removed_count, "confirmation_id": cid})
                decision.add_policy(title, "confirmed_cleanup", affected_rows=removed_count, confirmation_id=cid)
            else:
                item = upsert_confirmation(policy_state, {
                    "id": cid,
                    "type": "cleanup_confirmation",
                    "source": source,
                    "source_label": label,
                    "reason": effective_reason,
                    "affected_rows": removed_count,
                    "apply_mode": apply_mode,
                    "scope_hash": sh,
                    "codes": codes[:200],
                    "policy": action,
                }, expires_hours=confirm_hours)
                decision.requires_confirmation = True
                decision.confirmation_items.append(item)
                decision.preserve_codes.extend(codes)
                decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "requires_confirmation", "affected_rows": removed_count, "confirmation_id": cid})
                decision.add_recommendation(
                    f"Confirm {label} cleanup",
                    f"{removed_count} {label} row(s) are pending cleanup because {effective_reason.replace('_', ' ')}.",
                    "Open Policy Center and confirm cleanup, or adjust/re-enable the source if this was not intentional.",
                    severity="high",
                    confirmation_id=cid,
                )
        elif action == "warn_only":
            decision.preserve_codes.extend(codes)
            decision.add_warning(title, f"{removed_count} row(s) would be stale, but cleanup is warn-only by policy.", severity="warning")
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "warn_only", "affected_rows": removed_count})
        elif action == "block_cleanup":
            decision.preserve_codes.extend(codes)
            decision.add_warning(title, f"Cleanup blocked for {removed_count} row(s). Existing rows are preserved.", severity="high")
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "blocked_cleanup", "affected_rows": removed_count})
            decision.add_policy(title, "block_cleanup", affected_rows=removed_count)
        elif action == "block_apply":
            decision.preserve_codes.extend(codes)
            decision.add_block(title, f"Apply blocked because {removed_count} row(s) triggered {effective_reason.replace('_',' ')} cleanup policy.", source=source, affected_rows=removed_count)
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "block_apply", "affected_rows": removed_count})
        else:
            decision.preserve_codes.extend(codes)
            decision.cleanup_decisions.append({"source": source, "reason": effective_reason, "action": action, "decision": "preserve", "affected_rows": removed_count})

    return decision.finalize()


def evaluate_apply_guards(config: dict, decision: PolicyDecision, preflight: dict, result: Any) -> PolicyDecision:
    pol = policies(config)
    guard = pol.get("apply_guard", {}) or {}
    errors = preflight.get("errors", []) or []
    warnings = preflight.get("warnings", []) or []
    lower_errors = "\n".join(str(e).lower() for e in errors)
    if guard.get("block_apply_on_duplicate_ip", True) and "duplicate ip" in lower_errors:
        decision.add_block("Duplicate IP detected", "Preflight detected duplicate IP addresses. File write and LibreQoS apply are blocked.")
    if guard.get("block_apply_on_missing_parent", True) and "parent" in lower_errors:
        decision.add_block("Missing parent node", "One or more circuits reference missing Parent Node values. File write and LibreQoS apply are blocked.")
    if guard.get("block_apply_on_invalid_speed", True) and ("bandwidth" in lower_errors or "speed" in lower_errors):
        decision.add_block("Invalid speed/bandwidth", "Preflight detected invalid speed or bandwidth values. File write and LibreQoS apply are blocked.")
    if guard.get("block_apply_on_collector_failure", True) and getattr(result, "router_errors", None):
        decision.add_block("Collector failure", "One or more router/source collectors failed. Existing rows are preserved and apply is blocked by policy.", router_errors=getattr(result, "router_errors", []))
    for warn in warnings:
        if "fallback" in str(warn).lower():
            decision.add_warning("Fallback speed warning", str(warn), severity="warning")
    backup_guard = pol.get("backup_guard", {}) or {}
    if backup_guard.get("warn_if_backup_disabled_while_auto_apply_enabled", True):
        if config.get("app", {}).get("auto_apply", True) and not config.get("app", {}).get("backup_before_apply", True):
            decision.add_warning("Backup before apply is disabled", "Auto-apply is enabled but backup_before_apply is disabled.", severity="warning")
            decision.add_recommendation("Enable backup_before_apply", "Backups make rollback safer when auto-apply is enabled.", "Enable backup_before_apply in Config Center.", severity="warning")
    return decision.finalize()


def build_cleanup_candidates(existing_data: dict, active_codes_by_source: dict, cleanup_sources: set[str], static_comment_value: str = "static") -> list[dict[str, Any]]:
    from rules.cleanup import infer_row_source
    candidates = []
    static_value = str(static_comment_value or "static").strip().lower()
    active = {str(k).upper(): set(v or set()) for k, v in (active_codes_by_source or {}).items()}
    for code, row in list((existing_data or {}).items()):
        if str(row.get("Comment", "")).strip().lower() == static_value:
            continue
        source = infer_row_source(code, row)
        if source not in cleanup_sources:
            continue
        if code not in active.get(source, set()):
            candidates.append({"code": code, "source": source, "parent_node": row.get("Parent Node", ""), "circuit_name": row.get("Circuit Name", code), "row": dict(row)})
    return candidates


def existing_source_counts(existing_data: dict, static_comment_value: str = "static") -> dict[str, int]:
    from rules.cleanup import infer_row_source
    counts = defaultdict(int)
    static_value = str(static_comment_value or "static").strip().lower()
    for code, row in (existing_data or {}).items():
        if str(row.get("Comment", "")).strip().lower() == static_value:
            counts["STATIC"] += 1
            continue
        counts[infer_row_source(code, row)] += 1
    return dict(counts)


def update_successful_source_counts(policy_state: dict, source_success: set[str], active_counts: dict[str, int], node_counts: dict[str, int] | None = None) -> None:
    source_counts = policy_state.setdefault("last_successful_source_counts", {})
    for src in source_success:
        source_counts[src] = int(active_counts.get(src, 0) or 0)
    if node_counts:
        policy_state["last_successful_node_counts"] = {str(k): int(v) for k, v in node_counts.items()}
