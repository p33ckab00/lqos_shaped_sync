"""Notification delivery helpers for LQoSync.

v2.71 keeps Telegram delivery safe by default while splitting it into two
independent lanes:

- Safety alerts: urgent failures / policy holds that should be hard to miss.
- Activity journal: digest-first operational events such as client changes and
  successful LibreQoS applies.

Telegram still remains optional and dependency-free: it is disabled unless the
operator explicitly configures it.
"""
from __future__ import annotations

import hashlib
import html
import json
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALERT_EVENT_TOGGLES = {
    "source_health_warning": "notify_on_source_health_warning",
    "performance_slow": "notify_on_performance_slow",
    "apply_failed": "notify_on_apply_failed",
    "apply_warning": "notify_on_apply_failed",
    "policy_block": "notify_on_policy_block",
    "confirmation_required": "notify_on_confirmation_required",
    "update_available": "notify_on_update_available",
}

ACTIVITY_EVENT_TOGGLES = {
    "client_changes": "notify_on_client_changes",
    "apply_success": "notify_on_apply_success",
    "files_written": "notify_on_files_written",
}


def _cfg(config: dict[str, Any]) -> dict[str, Any]:
    return ((config or {}).get("notifications") or {}).get("telegram") or {}


def _state_path(config: dict[str, Any]) -> Path:
    paths = (config or {}).get("paths") or {}
    if paths.get("notification_state"):
        return Path(paths["notification_state"])
    if paths.get("runtime_state"):
        return Path(paths["runtime_state"]).with_name("notification_state.json")
    return Path("state/notification_state.json")


def mask_secret(secret: str | None, keep: int = 4) -> str:
    if not secret:
        return ""
    secret = str(secret)
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}…{secret[-keep:]}"


def telegram_settings_summary(config: dict[str, Any]) -> dict[str, Any]:
    tg = _cfg(config)
    token = str(tg.get("bot_token") or "")
    chat_id = str(tg.get("chat_id") or "")
    return {
        "enabled": bool(tg.get("enabled", False)),
        "configured": bool(token and chat_id),
        "token_masked": mask_secret(token),
        "chat_id_masked": mask_secret(chat_id, keep=3),
        "notify_levels": list(tg.get("notify_levels") or ["critical", "warning"]),
        "minimum_interval_seconds": int(tg.get("minimum_interval_seconds") or 60),
        "dedupe_window_minutes": int(tg.get("dedupe_window_minutes") or 60),
        "max_items_per_digest": int(tg.get("max_items_per_digest") or 10),
        "safety_alerts_enabled": bool(tg.get("safety_alerts_enabled", True)),
        "send_digest": bool(tg.get("send_digest", True)),
        "send_individual": bool(tg.get("send_individual", False)),
        "activity_journal_enabled": bool(tg.get("activity_journal_enabled", True)),
        "activity_send_digest": bool(tg.get("activity_send_digest", True)),
        "activity_send_individual": bool(tg.get("activity_send_individual", False)),
        "activity_silent_messages": bool(tg.get("activity_silent_messages", True)),
        "base_url": str(tg.get("base_url") or "").rstrip("/"),
        "parse_mode": str(tg.get("parse_mode") or "HTML"),
        "timeout_seconds": int(tg.get("timeout_seconds") or 10),
    }


def _load_state(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _notification_hash(item: dict[str, Any], lane: str = "alerts") -> str:
    explicit_key = item.get("dedupe_key")
    if explicit_key:
        basis = "|".join([lane, str(item.get("event") or ""), str(explicit_key)])
    else:
        basis = "|".join([
            lane,
            str(item.get("level") or ""),
            str(item.get("event") or ""),
            str(item.get("title") or ""),
            str(item.get("message") or ""),
            str(item.get("target") or ""),
        ])
    return hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()[:20]


def filter_notification_candidates(config: dict[str, Any], candidates: list[dict[str, Any]] | None, *, lane: str = "alerts") -> list[dict[str, Any]]:
    settings = telegram_settings_summary(config)
    allowed = {str(x).lower() for x in settings.get("notify_levels") or []}
    out = []
    event_to_toggle = ACTIVITY_EVENT_TOGGLES if lane == "activity" else ALERT_EVENT_TOGGLES
    tg = _cfg(config)
    for item in candidates or []:
        level = str(item.get("level") or "info").lower()
        # Activity journal entries are intentionally informational and should
        # not disappear just because production alert levels stay warning+
        # critical.
        if lane != "activity" and allowed and level not in allowed:
            continue
        event = str(item.get("event") or "").lower()
        toggle = event_to_toggle.get(event)
        if toggle and not bool(tg.get(toggle, True)):
            continue
        out.append(item)
    return out


def _format_item(item: dict[str, Any], base_url: str = "") -> str:
    level = html.escape(str(item.get("level") or "info").upper())
    title = html.escape(str(item.get("title") or "LQoSync notification"))
    message = html.escape(str(item.get("message") or ""))
    target = str(item.get("target") or "")
    target_line = ""
    if base_url and target:
        if target.startswith("/"):
            target_line = f"\nOpen: {html.escape(base_url + target)}"
        elif target.startswith("http://") or target.startswith("https://"):
            target_line = f"\nOpen: {html.escape(target)}"
    return f"<b>[{level}] {title}</b>\n{message}{target_line}"


def format_digest_message(config: dict[str, Any], notifications: list[dict[str, Any]], title: str | None = None) -> str:
    settings = telegram_settings_summary(config)
    base_url = str(settings.get("base_url") or "")
    max_items = int(settings.get("max_items_per_digest") or 10)
    host = socket.gethostname()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = html.escape(title or "LQoSync notification digest")
    lines = [f"<b>{header}</b>", f"Host: <code>{html.escape(host)}</code>", f"Time: <code>{html.escape(now)}</code>"]
    if not notifications:
        lines.append("No notification-worthy conditions detected.")
    else:
        shown = notifications[:max_items]
        for idx, item in enumerate(shown, 1):
            lines.append(f"\n{idx}. " + _format_item(item, base_url=base_url))
        extra = len(notifications) - len(shown)
        if extra > 0:
            lines.append(f"\n…and {extra} more item(s).")
    return "\n".join(lines)


def send_telegram_message(config: dict[str, Any], text: str, *, disable_notification: bool = False) -> dict[str, Any]:
    tg = _cfg(config)
    token = str(tg.get("bot_token") or "").strip()
    chat_id = str(tg.get("chat_id") or "").strip()
    if not token or not chat_id:
        return {"ok": False, "error": "telegram_not_configured"}
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
        "disable_notification": "true" if disable_notification else "false",
    }
    parse_mode = str(tg.get("parse_mode") or "HTML").strip()
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    timeout = int(tg.get("timeout_seconds") or 10)
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {"ok": bool(parsed.get("ok", False)), "status": resp.status, "response": parsed}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def send_test_message(config: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
    actor_line = f"\nTriggered by: <code>{html.escape(actor)}</code>" if actor else ""
    msg = (
        "<b>LQoSync Telegram test</b>\n"
        "Telegram notifications are configured and reachable.\n"
        f"Host: <code>{html.escape(socket.gethostname())}</code>"
        f"{actor_line}"
    )
    return send_telegram_message(config, msg)


def _lane_state(state: dict[str, Any], lane: str) -> dict[str, Any]:
    lanes = state.setdefault("lanes", {})
    if not isinstance(lanes, dict):
        lanes = state["lanes"] = {}
    if lane not in lanes or not isinstance(lanes.get(lane), dict):
        # Preserve the pre-v2.71 single-lane state as the alerts lane so
        # upgrades keep their existing dedupe/rate-limit history.
        if lane == "alerts" and any(k in state for k in ("last_sent_at", "sent_hashes", "last_result")):
            lanes[lane] = {
                "last_sent_at": state.get("last_sent_at") or 0,
                "sent_hashes": dict(state.get("sent_hashes") or {}),
                "last_result": state.get("last_result") or {},
            }
        else:
            lanes[lane] = {}
    return lanes[lane]


def dispatch_telegram_notifications(
    config: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    force: bool = False,
    title: str | None = None,
    lane: str = "alerts",
) -> dict[str, Any]:
    lane = "activity" if lane == "activity" else "alerts"
    settings = telegram_settings_summary(config)
    if not settings.get("enabled") and not force:
        return {"ok": False, "skipped": True, "reason": "telegram_disabled", "sent": 0, "lane": lane}
    if not settings.get("configured"):
        return {"ok": False, "skipped": True, "reason": "telegram_not_configured", "sent": 0, "lane": lane}
    if lane == "activity" and not settings.get("activity_journal_enabled") and not force:
        return {"ok": False, "skipped": True, "reason": "activity_journal_disabled", "sent": 0, "lane": lane}
    if lane == "alerts" and not settings.get("safety_alerts_enabled") and not force:
        return {"ok": False, "skipped": True, "reason": "safety_alerts_disabled", "sent": 0, "lane": lane}

    filtered = filter_notification_candidates(config, candidates, lane=lane)
    if not filtered:
        return {"ok": True, "skipped": True, "reason": "no_matching_notifications", "sent": 0, "lane": lane}

    path = _state_path(config)
    state = _load_state(path)
    lane_state = _lane_state(state, lane)
    now = int(time.time())
    min_interval = int(settings.get("minimum_interval_seconds") or 60)
    dedupe_window = int(settings.get("dedupe_window_minutes") or 60) * 60
    last_sent_at = int(lane_state.get("last_sent_at") or 0)
    if not force and last_sent_at and now - last_sent_at < min_interval:
        return {"ok": False, "skipped": True, "reason": "minimum_interval_active", "sent": 0, "retry_after_seconds": min_interval - (now - last_sent_at), "lane": lane}

    sent_hashes = lane_state.setdefault("sent_hashes", {})
    deliverable = []
    for item in filtered:
        h = _notification_hash(item, lane=lane)
        item = dict(item)
        item["hash"] = h
        previous = int(sent_hashes.get(h) or 0)
        if not force and previous and now - previous < dedupe_window:
            continue
        deliverable.append(item)

    if not deliverable:
        return {"ok": True, "skipped": True, "reason": "all_notifications_deduped", "sent": 0, "lane": lane}

    send_digest = settings.get("activity_send_digest") if lane == "activity" else settings.get("send_digest")
    send_individual = settings.get("activity_send_individual") if lane == "activity" else settings.get("send_individual")
    disable_notification = bool(settings.get("activity_silent_messages")) if lane == "activity" else False
    if send_individual and not send_digest:
        results = []
        for item in deliverable:
            res = send_telegram_message(config, _format_item(item, base_url=settings.get("base_url") or ""), disable_notification=disable_notification)
            results.append(res)
            if res.get("ok"):
                sent_hashes[item["hash"]] = now
        ok_count = sum(1 for r in results if r.get("ok"))
        lane_state["last_sent_at"] = now if ok_count else last_sent_at
        lane_state["last_result"] = {"ok_count": ok_count, "results": results[-5:], "sent_at": now, "lane": lane}
        _save_state(path, state)
        return {"ok": ok_count > 0, "sent": ok_count, "mode": "individual", "results": results, "lane": lane}

    default_title = "LQoSync activity journal" if lane == "activity" else "LQoSync alert digest"
    message = format_digest_message(config, deliverable, title=title or default_title)
    res = send_telegram_message(config, message, disable_notification=disable_notification)
    if res.get("ok"):
        for item in deliverable:
            sent_hashes[item["hash"]] = now
        lane_state["last_sent_at"] = now
        lane_state["last_result"] = {"ok": True, "sent": len(deliverable), "sent_at": now, "mode": "digest", "lane": lane}
        _save_state(path, state)
        return {"ok": True, "sent": len(deliverable), "mode": "digest", "response": res, "lane": lane}
    lane_state["last_result"] = {"ok": False, "error": res.get("error"), "sent_at": now, "lane": lane}
    _save_state(path, state)
    return {"ok": False, "sent": 0, "mode": "digest", "response": res, "error": res.get("error"), "lane": lane}


def _result_attr(result: Any, key: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _result_diff(result: Any) -> dict[str, Any]:
    diff = _result_attr(result, "diff", {})
    return diff if isinstance(diff, dict) else {}


def _policy_message(policy_decision: dict[str, Any]) -> str:
    blocked = policy_decision.get("blocked_reasons") or []
    if blocked:
        return "; ".join(str(item.get("message") or item.get("title") or "Policy blocked apply") for item in blocked[:3])
    confirmations = policy_decision.get("confirmation_items") or []
    if confirmations:
        return f"{len(confirmations)} cleanup confirmation item(s) require operator review before apply."
    return "Policy requires operator review before apply."


def build_runtime_safety_notifications(result: Any) -> list[dict[str, Any]]:
    """Build urgent notifications from one completed runtime action."""
    diff = _result_diff(result)
    policy = diff.get("policy_decision") or {}
    status = str(_result_attr(result, "status", "") or "")
    started_at = str(_result_attr(result, "started_at", "") or "")
    items: list[dict[str, Any]] = []

    if isinstance(policy, dict) and policy.get("requires_confirmation"):
        items.append({
            "level": "warning",
            "event": "confirmation_required",
            "title": "Cleanup confirmation required",
            "message": _policy_message(policy),
            "target": "/lifecycle",
            "dedupe_key": f"confirmation:{started_at}:{policy.get('risk_score', '')}",
        })
    if (status == "policy_blocked" and not bool(policy.get("requires_confirmation"))) or (isinstance(policy, dict) and policy.get("blocked_reasons")):
        items.append({
            "level": "critical" if str(policy.get("risk_level") or "") == "critical" else "warning",
            "event": "policy_block",
            "title": "Policy blocked live apply",
            "message": _policy_message(policy if isinstance(policy, dict) else {}),
            "target": "/#policy-decision",
            "dedupe_key": f"policy_block:{started_at}:{policy.get('risk_score', '') if isinstance(policy, dict) else ''}",
        })
    if status == "libreqos_failed" or (
        bool(_result_attr(result, "libreqos_triggered", False))
        and _result_attr(result, "libreqos_exit_code", 0) not in (None, 0)
    ):
        run_id = diff.get("libreqos_run_id")
        reason = diff.get("libreqos_apply_reason") or "apply"
        target = f"/libreqos/apply/{run_id}" if run_id else "/operations?tab=apply"
        items.append({
            "level": "critical",
            "event": "apply_failed",
            "title": "LibreQoS apply failed",
            "message": f"LibreQoS apply failed during {reason}. Exit code: {_result_attr(result, 'libreqos_exit_code', 'unknown')}.",
            "target": target,
            "dedupe_key": f"apply_failed:{run_id or started_at}",
        })
    return items


def build_runtime_activity_notifications(result: Any) -> list[dict[str, Any]]:
    """Build digest-first operational journal items from one sync result."""
    diff = _result_diff(result)
    summary = diff.get("client_change_summary") or {}
    counts = summary.get("counts") or {}
    total = int(counts.get("total") or 0)
    started_at = str(_result_attr(result, "started_at", "") or "")
    items: list[dict[str, Any]] = []

    if total:
        preview = str(summary.get("clients_preview") or "").strip()
        msg = str(summary.get("summary_text") or f"{total} client change(s)")
        if preview:
            msg += f". Clients: {preview}."
        items.append({
            "level": "info",
            "event": "client_changes",
            "title": "Client records changed",
            "message": msg,
            "target": "/operations?tab=audit",
            "dedupe_key": f"client_changes:{started_at}:{counts.get('added', 0)}:{counts.get('updated', 0)}:{counts.get('removed', 0)}",
        })
    elif bool(_result_attr(result, "files_changed", False)):
        items.append({
            "level": "info",
            "event": "files_written",
            "title": "Generated files changed",
            "message": "ShapedDevices.csv or network.json changed without client-row changes.",
            "target": "/operations?tab=audit",
            "dedupe_key": f"files_written:{started_at}",
        })

    if bool(_result_attr(result, "libreqos_triggered", False)) and _result_attr(result, "libreqos_exit_code", 0) in (None, 0):
        run_id = diff.get("libreqos_run_id")
        reason = diff.get("libreqos_apply_reason") or "apply"
        target = f"/libreqos/apply/{run_id}" if run_id else "/operations?tab=apply"
        items.append({
            "level": "info",
            "event": "apply_success",
            "title": "LibreQoS apply completed",
            "message": f"LibreQoS apply succeeded ({reason})" + (f". Run ID: {run_id}." if run_id else "."),
            "target": target,
            "dedupe_key": f"apply_success:{run_id or started_at}",
        })
    return items


def build_force_apply_notifications(apply_result: dict[str, Any], *, reason: str = "force_apply") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (alerts, activity) for direct/manual LibreQoS apply routes."""
    run_id = apply_result.get("run_id")
    target = f"/libreqos/apply/{run_id}" if run_id else "/operations?tab=apply"
    if apply_result.get("ok"):
        return [], [{
            "level": "info",
            "event": "apply_success",
            "title": "LibreQoS apply completed",
            "message": f"LibreQoS apply succeeded ({reason})" + (f". Run ID: {run_id}." if run_id else "."),
            "target": target,
            "dedupe_key": f"apply_success:{run_id or reason}",
        }]
    return [{
        "level": "critical",
        "event": "apply_failed",
        "title": "LibreQoS apply failed",
        "message": f"LibreQoS apply failed during {reason}. Exit code: {apply_result.get('exit_code', 'unknown')}.",
        "target": target,
        "dedupe_key": f"apply_failed:{run_id or reason}",
    }], []
