"""Universal speed resolver for PPPoE, DHCP, and Hotspot sources.

The resolver returns the resolved download/upload Mbps plus the exact source
that won. This makes dry-run, audit, Dashboard timeline, and Shaped Devices
explanations consistent across all collectors.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from parsers.bandwidth import parse_comment_bandwidth, parse_rate_limit
from parsers.profile import parse_speed_from_profile_name


@dataclass
class SpeedResolution:
    download_mbps: float
    upload_mbps: float
    source: str
    raw_value: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _from_text(raw: Any, source: str, priority: int, parser: str = "comment") -> SpeedResolution | None:
    text = _clean(raw)
    if not text:
        return None
    if parser == "rate_limit":
        rx, tx = parse_rate_limit(text)
        if rx > 0 and tx > 0:
            return SpeedResolution(float(rx), float(tx), source, text, priority)
        return None
    if parser == "profile_name":
        parsed = parse_speed_from_profile_name(text)
        if parsed:
            return SpeedResolution(float(parsed[0]), float(parsed[1]), source, text, priority)
        return None
    parsed = parse_comment_bandwidth(text)
    if parsed:
        return SpeedResolution(float(parsed[0]), float(parsed[1]), source, text, priority)
    return None


def _from_config(down: Any, up: Any, source: str, raw_value: str, priority: int) -> SpeedResolution | None:
    try:
        rx = float(down)
        tx = float(up)
    except Exception:
        return None
    if rx <= 0 or tx <= 0:
        return None
    return SpeedResolution(rx, tx, source, raw_value, priority)


def resolve_pppoe_speed(secret: dict, active_row: dict, profile: dict | None, profile_name: str, default_rate: str) -> SpeedResolution:
    profile = profile or {}
    candidates = [
        (secret.get("comment"), "ppp_secret_comment", 1, "comment"),
        (active_row.get("comment"), "ppp_active_comment", 2, "comment"),
        (profile.get("comment"), "ppp_profile_comment", 3, "comment"),
        (profile_name, "ppp_profile_name", 4, "profile_name"),
        (profile.get("rate-limit"), "ppp_profile_rate_limit", 5, "rate_limit"),
        (default_rate, "config_default_pppoe", 6, "rate_limit"),
    ]
    for raw, source, priority, parser in candidates:
        resolved = _from_text(raw, source, priority, parser)
        if resolved:
            return resolved
    return SpeedResolution(10.0, 10.0, "config_default_pppoe_fallback", _clean(default_rate) or "10M/10M", 99)


def resolve_dhcp_speed(server_cfg: dict, server_meta: dict | None, defaults: dict) -> SpeedResolution:
    server_meta = server_meta or {}
    server_name = _clean(server_cfg.get("name") or server_meta.get("name"))
    # DHCP dynamic leases do not reliably support operator comments, so speed
    # is resolved from server-level information and config defaults.
    server_speed_text = (
        _clean(server_cfg.get("speed_comment"))
        or _clean(server_cfg.get("plan_comment"))
        or _clean(server_cfg.get("description"))
        or _clean(server_meta.get("comment"))
    )
    candidates = [
        (server_speed_text, "dhcp_server_comment", 1, "comment"),
        (server_name, "dhcp_server_name", 2, "profile_name"),
    ]
    for raw, source, priority, parser in candidates:
        resolved = _from_text(raw, source, priority, parser)
        if resolved:
            return resolved

    down = server_cfg.get("default_plan_down_mbps", server_cfg.get("download_limit_mbps"))
    up = server_cfg.get("default_plan_up_mbps", server_cfg.get("upload_limit_mbps"))
    resolved = _from_config(down, up, "dhcp_server_config", f"{down}/{up}", 3)
    if resolved:
        return resolved
    default_mbps = defaults.get("default_dhcp_per_client_mbps", 15)
    resolved = _from_config(default_mbps, default_mbps, "config_default_dhcp", str(default_mbps), 4)
    if resolved:
        return resolved
    return SpeedResolution(15.0, 15.0, "config_default_dhcp_fallback", "15", 99)


def resolve_hotspot_speed(active_row: dict, user: dict | None, profile: dict | None, hs_cfg: dict, defaults: dict) -> SpeedResolution:
    user = user or {}
    profile = profile or {}
    profile_name = _clean(user.get("profile") or profile.get("name"))
    candidates = [
        (user.get("comment"), "hotspot_user_comment", 1, "comment"),
        (profile.get("comment"), "hotspot_profile_comment", 2, "comment"),
        (profile_name, "hotspot_profile_name", 3, "profile_name"),
        (profile.get("rate-limit"), "hotspot_profile_rate_limit", 4, "rate_limit"),
    ]
    for raw, source, priority, parser in candidates:
        resolved = _from_text(raw, source, priority, parser)
        if resolved:
            return resolved

    down = hs_cfg.get("download_limit_mbps", defaults.get("default_hotspot_per_client_mbps", 10))
    up = hs_cfg.get("upload_limit_mbps", defaults.get("default_hotspot_per_client_mbps", 10))
    resolved = _from_config(down, up, "hotspot_config_speed", f"{down}/{up}", 5)
    if resolved:
        return resolved
    default_mbps = defaults.get("default_hotspot_per_client_mbps", 10)
    return SpeedResolution(float(default_mbps), float(default_mbps), "config_default_hotspot", str(default_mbps), 6)


def friendly_speed_source(source: str) -> str:
    labels = {
        "ppp_secret_comment": "PPP secret comment",
        "ppp_active_comment": "PPP active comment",
        "ppp_profile_comment": "PPP profile comment",
        "ppp_profile_name": "PPP profile name",
        "ppp_profile_rate_limit": "PPP profile rate-limit",
        "config_default_pppoe": "Default PPPoE rate",
        "dhcp_server_comment": "DHCP server comment",
        "dhcp_server_name": "DHCP server name",
        "dhcp_server_config": "DHCP server config speed",
        "config_default_dhcp": "Default DHCP speed",
        "hotspot_user_comment": "Hotspot user comment",
        "hotspot_profile_comment": "Hotspot profile comment",
        "hotspot_profile_name": "Hotspot profile name",
        "hotspot_profile_rate_limit": "Hotspot profile rate-limit",
        "hotspot_config_speed": "Hotspot config speed",
        "config_default_hotspot": "Default Hotspot speed",
    }
    return labels.get(source, source.replace("_", " ").title())
