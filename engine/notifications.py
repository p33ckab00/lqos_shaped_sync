"""Notification delivery helpers for LQoSync.

v2.58 focuses on Telegram delivery for existing internal notification candidates.
The module is intentionally small, dependency-free, and safe by default:
Telegram is disabled unless explicitly configured by the operator.
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


def _cfg(config: dict[str, Any]) -> dict[str, Any]:
    return ((config or {}).get("notifications") or {}).get("telegram") or {}


def _state_path(config: dict[str, Any]) -> Path:
    paths = (config or {}).get("paths") or {}
    return Path(paths.get("notification_state") or "state/notification_state.json")


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
        "send_digest": bool(tg.get("send_digest", True)),
        "send_individual": bool(tg.get("send_individual", False)),
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


def _notification_hash(item: dict[str, Any]) -> str:
    basis = "|".join([
        str(item.get("level") or ""),
        str(item.get("title") or ""),
        str(item.get("message") or ""),
        str(item.get("target") or ""),
    ])
    return hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()[:20]


def filter_notification_candidates(config: dict[str, Any], candidates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    settings = telegram_settings_summary(config)
    allowed = {str(x).lower() for x in settings.get("notify_levels") or []}
    out = []
    event_to_toggle = {
        "source_health_warning": "notify_on_source_health_warning",
        "performance_slow": "notify_on_performance_slow",
        "apply_failed": "notify_on_apply_failed",
        "apply_warning": "notify_on_apply_failed",
        "policy_block": "notify_on_policy_block",
        "confirmation_required": "notify_on_confirmation_required",
        "update_available": "notify_on_update_available",
    }
    tg = _cfg(config)
    for item in candidates or []:
        level = str(item.get("level") or "info").lower()
        if allowed and level not in allowed:
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


def dispatch_telegram_notifications(config: dict[str, Any], candidates: list[dict[str, Any]], *, force: bool = False, title: str | None = None) -> dict[str, Any]:
    settings = telegram_settings_summary(config)
    if not settings.get("enabled") and not force:
        return {"ok": False, "skipped": True, "reason": "telegram_disabled", "sent": 0}
    if not settings.get("configured"):
        return {"ok": False, "skipped": True, "reason": "telegram_not_configured", "sent": 0}

    filtered = filter_notification_candidates(config, candidates)
    if not filtered:
        return {"ok": True, "skipped": True, "reason": "no_matching_notifications", "sent": 0}

    path = _state_path(config)
    state = _load_state(path)
    now = int(time.time())
    min_interval = int(settings.get("minimum_interval_seconds") or 60)
    dedupe_window = int(settings.get("dedupe_window_minutes") or 60) * 60
    last_sent_at = int(state.get("last_sent_at") or 0)
    if not force and last_sent_at and now - last_sent_at < min_interval:
        return {"ok": False, "skipped": True, "reason": "minimum_interval_active", "sent": 0, "retry_after_seconds": min_interval - (now - last_sent_at)}

    sent_hashes = state.setdefault("sent_hashes", {})
    deliverable = []
    for item in filtered:
        h = _notification_hash(item)
        item = dict(item)
        item["hash"] = h
        previous = int(sent_hashes.get(h) or 0)
        if not force and previous and now - previous < dedupe_window:
            continue
        deliverable.append(item)

    if not deliverable:
        return {"ok": True, "skipped": True, "reason": "all_notifications_deduped", "sent": 0}

    if settings.get("send_individual") and not settings.get("send_digest"):
        results = []
        for item in deliverable:
            res = send_telegram_message(config, _format_item(item, base_url=settings.get("base_url") or ""))
            results.append(res)
            if res.get("ok"):
                sent_hashes[item["hash"]] = now
        ok_count = sum(1 for r in results if r.get("ok"))
        state["last_sent_at"] = now if ok_count else last_sent_at
        state["last_result"] = {"ok_count": ok_count, "results": results[-5:], "sent_at": now}
        _save_state(path, state)
        return {"ok": ok_count > 0, "sent": ok_count, "mode": "individual", "results": results}

    message = format_digest_message(config, deliverable, title=title or "LQoSync alert digest")
    res = send_telegram_message(config, message)
    if res.get("ok"):
        for item in deliverable:
            sent_hashes[item["hash"]] = now
        state["last_sent_at"] = now
        state["last_result"] = {"ok": True, "sent": len(deliverable), "sent_at": now, "mode": "digest"}
        _save_state(path, state)
        return {"ok": True, "sent": len(deliverable), "mode": "digest", "response": res}
    state["last_result"] = {"ok": False, "error": res.get("error"), "sent_at": now}
    _save_state(path, state)
    return {"ok": False, "sent": 0, "mode": "digest", "response": res, "error": res.get("error")}
