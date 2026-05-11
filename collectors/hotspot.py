import time
from collectors.mikrotik_client import read_resource
from builders.circuit_rows import create_new_entry, update_entry_values, calculate_user_min_max
from builders.node_tree import hotspot_node_name, make_node
from parsers.identity import build_hotspot_code, clean_mac
from parsers.speed_resolver import resolve_hotspot_speed
from validators.duplicate_checker import check_duplicate_ip
from rules.network_mode import parent_for_flat_mode
from engine.collector_cache import stable_hash, get_source, set_source

HS_ACTIVE_FIELDS = ["user", "address", "mac-address", "server", "comment"]
HS_USER_FIELDS = ["name", "profile", "comment"]
HS_PROFILE_FIELDS = ["name", "comment", "rate-limit"]


def _cache_key(router_name: str, suffix: str) -> str:
    return f"{router_name}:hotspot:{suffix}"


def _record_source_hash(context, key: str, rows: list):
    h = stable_hash(rows)
    previous = get_source(context.cache, key)
    if previous.get("hash") == h:
        context.cache_metrics["hits"] = context.cache_metrics.get("hits", 0) + 1
    else:
        context.cache_metrics["misses"] = context.cache_metrics.get("misses", 0) + 1
        context.cache_metrics["changes"] = context.cache_metrics.get("changes", 0) + 1
    set_source(context.cache, key, {"hash": h, "count": len(rows)})
    return h


def process_hotspot_users(api, router: dict, context):
    hs_cfg = router.get("hotspot", {})
    if not hs_cfg.get("enabled", False):
        return set(), False
    cfg = context.config
    defaults = cfg["defaults"]
    collector_hs_cfg = cfg.get("collector", {}).get("hotspot", {})
    enhanced = bool(collector_hs_cfg.get("enhanced_metadata", hs_cfg.get("enhanced_metadata", False)))
    router_name = router["name"]
    flat_parent = parent_for_flat_mode(cfg, router_name)
    hierarchy_mode = flat_parent is None
    children = context.network_config.get(router_name, {}).get("children", {}) if hierarchy_mode else {}
    include_mac = bool(hs_cfg.get("include_mac", True))
    dl_factor = float(hs_cfg.get("download_factor", 1.0))
    ul_factor = float(hs_cfg.get("upload_factor", 1.0))
    node_name = hotspot_node_name(router)
    parent_node = node_name if hierarchy_mode else flat_parent
    active_codes = set()
    updated = False

    t = time.perf_counter()
    active_rows = read_resource(api, "/ip/hotspot/active", cfg, HS_ACTIVE_FIELDS)
    active_read_ms = round((time.perf_counter() - t) * 1000, 3)
    users = []
    profiles = []
    users_read_ms = 0.0
    profiles_read_ms = 0.0
    if enhanced:
        t = time.perf_counter()
        users = read_resource(api, "/ip/hotspot/user", cfg, HS_USER_FIELDS)
        users_read_ms = round((time.perf_counter() - t) * 1000, 3)
        t = time.perf_counter()
        profiles = read_resource(api, "/ip/hotspot/user/profile", cfg, HS_PROFILE_FIELDS)
        profiles_read_ms = round((time.perf_counter() - t) * 1000, 3)
    _record_source_hash(context, _cache_key(router_name, "active"), active_rows)
    if enhanced:
        _record_source_hash(context, _cache_key(router_name, "users"), users)
        _record_source_hash(context, _cache_key(router_name, "profiles"), profiles)
    user_by_name = {str(u.get("name", "")).strip(): u for u in users if u.get("name")}
    profile_by_name = {str(p.get("name", "")).strip(): p for p in profiles if p.get("name")}

    total_down = 0.0
    total_up = 0.0
    parse_t = time.perf_counter()
    for user in active_rows:
        mac = str(user.get("mac-address", "")).strip()
        ip = str(user.get("address", "")).strip()
        username = str(user.get("user", "")).strip()
        code = build_hotspot_code(username, mac, include_mac)
        if not code:
            context.warnings.append(f"Skipping Hotspot active row with no username/mac: ip={ip}")
            continue
        user_meta = user_by_name.get(username, {}) if enhanced else {}
        profile_name = str(user_meta.get("profile", "")).strip()
        profile_meta = profile_by_name.get(profile_name, {}) if enhanced else {}
        resolved = resolve_hotspot_speed(user, user_meta, profile_meta, hs_cfg, defaults)
        per_down, per_up = resolved.download_mbps, resolved.upload_mbps
        context.count_speed_source(resolved.source)
        active_codes.add(code)
        total_down += per_down
        total_up += per_up
        device_name = username or clean_mac(mac)
        if code not in context.existing_data:
            if ip and check_duplicate_ip(context.existing_data, ip, code, context):
                continue
            context.existing_data[code] = create_new_entry(code, device_name, defaults.get("id_length", 8), mac=mac, ipv4=ip, comment="HS")
            updated = True
        rx_min, tx_min, rx_max, tx_max = calculate_user_min_max(per_down, per_up, float(defaults.get("min_rate_percentage", 0.5)))
        if update_entry_values(context.existing_data[code], {"Parent Node": parent_node, "MAC": mac, "IPv4": ip, "Download Min Mbps": rx_min, "Upload Min Mbps": tx_min, "Download Max Mbps": rx_max, "Upload Max Mbps": tx_max, "Comment": "HS"}):
            updated = True
        context.meta[code] = {"source_type": "HS", "router": router_name, "base_rx": per_down, "base_tx": per_up, "speed_source": resolved.source, "speed_raw_value": resolved.raw_value, "speed_priority": resolved.priority, "profile": profile_name}
    parse_ms = round((time.perf_counter() - parse_t) * 1000, 3)
    if active_codes and hierarchy_mode:
        final_rx = total_down * dl_factor
        final_tx = total_up * ul_factor
        new_node = make_node(final_rx, final_tx, hs_cfg.get("node_type", "site"))
        context.node_math[node_name] = {
            "source": "Hotspot",
            "mode": "per_client",
            "active_count": len(active_codes),
            "raw_download_mbps": round(total_down, 3),
            "raw_upload_mbps": round(total_up, 3),
            "download_factor": dl_factor,
            "upload_factor": ul_factor,
            "final_download_mbps": new_node["downloadBandwidthMbps"],
            "final_upload_mbps": new_node["uploadBandwidthMbps"],
            "formula": f"sum {round(total_down,3)} Mbps × {dl_factor} = {new_node['downloadBandwidthMbps']} Mbps",
        }
        if children.get(node_name) != new_node:
            children[node_name] = new_node
            updated = True
    elif hierarchy_mode and node_name in children:
        del children[node_name]
        updated = True
    elif active_codes and not hierarchy_mode:
        context.node_math[f"HS-flat-{router_name}"] = {
            "source": "Hotspot",
            "mode": context.network_mode,
            "active_count": len(active_codes),
            "formula": "flat mode: Hotspot circuits point directly to router root" if flat_parent else "flat mode: Hotspot circuits use blank Parent Node",
        }
    context.collector_metrics[f"{router_name}.hotspot"] = {
        "source": "Hotspot",
        "active_users": len(active_rows),
        "users_loaded": len(users),
        "profiles_loaded": len(profiles),
        "generated_rows": len(active_codes),
        "enhanced_metadata": enhanced,
        "read_active_ms": active_read_ms,
        "read_users_ms": users_read_ms,
        "read_profiles_ms": profiles_read_ms,
        "parse_ms": parse_ms,
    }
    context.counts["hotspot"] += len(active_codes)
    context.add_source_codes("HS", active_codes)
    return active_codes, updated
