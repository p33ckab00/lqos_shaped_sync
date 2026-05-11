import time
from collectors.mikrotik_client import read_resource
from builders.circuit_rows import create_new_entry, update_entry_values, calculate_user_min_max
from builders.node_tree import ppp_plan_node_name, ppp_flat_node_name, factor_for_profile, make_node
from parsers.speed_resolver import resolve_pppoe_speed
from parsers.identity import build_pppoe_code
from validators.duplicate_checker import check_duplicate_ip
from rules.network_mode import parent_for_flat_mode
from engine.collector_cache import stable_hash, get_source, set_source

PPP_ACTIVE_FIELDS = ["name", "address", "caller-id", "comment"]
PPP_SECRET_FIELDS = ["name", "profile", "comment", "caller-id", "disabled", "inactive"]
PPP_PROFILE_FIELDS = ["name", "comment", "rate-limit"]


def _cache_key(router_name: str, suffix: str) -> str:
    return f"{router_name}:pppoe:{suffix}"


def _record_source_hash(context, key: str, rows: list, parsed_payload=None):
    h = stable_hash(rows)
    previous = get_source(context.cache, key)
    if previous.get("hash") == h:
        context.cache_metrics["hits"] = context.cache_metrics.get("hits", 0) + 1
    else:
        context.cache_metrics["misses"] = context.cache_metrics.get("misses", 0) + 1
        context.cache_metrics["changes"] = context.cache_metrics.get("changes", 0) + 1
    payload = {"hash": h, "count": len(rows)}
    if parsed_payload is not None:
        payload["parsed"] = parsed_payload
    set_source(context.cache, key, payload)
    return h


def process_pppoe_users(api, router: dict, context):
    if not router.get("pppoe", {}).get("enabled", False):
        return set(), False
    cfg = context.config
    defaults = cfg["defaults"]
    router_name = router["name"]
    flat_parent = parent_for_flat_mode(cfg, router_name)
    hierarchy_mode = flat_parent is None
    children = context.network_config.get(router_name, {}).get("children", {}) if hierarchy_mode else {}
    per_plan_node = router.get("pppoe", {}).get("per_plan_node", False)
    updated = False
    active_codes = set()

    t = time.perf_counter()
    active_rows = read_resource(api, "/ppp/active", cfg, PPP_ACTIVE_FIELDS)
    active_read_ms = round((time.perf_counter() - t) * 1000, 3)
    t = time.perf_counter()
    secret_rows = read_resource(api, "/ppp/secret", cfg, PPP_SECRET_FIELDS)
    secrets_read_ms = round((time.perf_counter() - t) * 1000, 3)
    t = time.perf_counter()
    profile_rows = read_resource(api, "/ppp/profile", cfg, PPP_PROFILE_FIELDS)
    profiles_read_ms = round((time.perf_counter() - t) * 1000, 3)

    _record_source_hash(context, _cache_key(router_name, "active"), active_rows)
    _record_source_hash(context, _cache_key(router_name, "secrets"), secret_rows)
    _record_source_hash(context, _cache_key(router_name, "profiles"), profile_rows)

    secrets = {
        s["name"]: s for s in secret_rows
        if s.get("name") and str(s.get("disabled", "false")).lower() == "false" and str(s.get("inactive", "false")).lower() == "false"
    }
    active = {a["name"]: a for a in active_rows if a.get("name")}
    profiles = {p["name"]: p for p in profile_rows if p.get("name")}

    flat_total_rx = 0.0
    flat_total_tx = 0.0
    plan_totals = {}
    skipped_no_secret = 0
    parse_t = time.perf_counter()
    for username in set(active) & set(secrets):
        active_row = active[username]
        secret = secrets[username]
        ip_address = str(active_row.get("address", "")).strip()
        mac = str(active_row.get("caller-id") or secret.get("caller-id") or "").strip()
        profile_name = str(secret.get("profile", defaults.get("default_pppoe_profile", "default"))).strip() or defaults.get("default_pppoe_profile", "default")
        profile = profiles.get(profile_name, {})
        code = build_pppoe_code(username, mac)
        if not code:
            continue
        active_codes.add(code)
        if code not in context.existing_data:
            if ip_address and check_duplicate_ip(context.existing_data, ip_address, code, context):
                continue
            context.existing_data[code] = create_new_entry(code, username or code, defaults.get("id_length", 8), mac=mac, ipv4=ip_address, comment="PPP")
            updated = True
        resolved = resolve_pppoe_speed(secret, active_row, profile, profile_name, defaults.get("default_pppoe_rate", "10M/10M"))
        base_rx, base_tx, speed_source = resolved.download_mbps, resolved.upload_mbps, resolved.source
        context.count_speed_source(speed_source)
        rx_min, tx_min, rx_max, tx_max = calculate_user_min_max(base_rx, base_tx, float(defaults.get("min_rate_percentage", 0.5)))
        if not hierarchy_mode:
            parent_node = flat_parent
        elif per_plan_node:
            parent_node = ppp_plan_node_name(router, profile_name)
            plan_totals.setdefault(parent_node, {"rx": 0.0, "tx": 0.0, "count": 0, "profile": profile_name})
            plan_totals[parent_node]["rx"] += base_rx
            plan_totals[parent_node]["tx"] += base_tx
            plan_totals[parent_node]["count"] += 1
        else:
            parent_node = ppp_flat_node_name(router)
            flat_total_rx += base_rx
            flat_total_tx += base_tx
        new_values = {"Parent Node": parent_node, "MAC": mac, "IPv4": ip_address, "Download Min Mbps": rx_min, "Upload Min Mbps": tx_min, "Download Max Mbps": rx_max, "Upload Max Mbps": tx_max, "Comment": "PPP"}
        if update_entry_values(context.existing_data[code], new_values):
            updated = True
        context.meta[code] = {"source_type": "PPP", "speed_source": speed_source, "speed_raw_value": resolved.raw_value, "speed_priority": resolved.priority, "profile": profile_name, "router": router_name, "base_rx": base_rx, "base_tx": base_tx}

    skipped_no_secret = max(0, len(set(active) - set(secrets)))
    parse_ms = round((time.perf_counter() - parse_t) * 1000, 3)
    context.collector_metrics[f"{router_name}.pppoe"] = {
        "source": "PPPoE",
        "active_sessions": len(active_rows),
        "active_matched": len(active_codes),
        "secrets_loaded": len(secret_rows),
        "profiles_loaded": len(profile_rows),
        "skipped_no_secret": skipped_no_secret,
        "generated_rows": len(active_codes),
        "read_active_ms": active_read_ms,
        "read_secrets_ms": secrets_read_ms,
        "read_profiles_ms": profiles_read_ms,
        "parse_ms": parse_ms,
    }

    if not hierarchy_mode:
        context.node_math[f"PPP-flat-{router_name}"] = {
            "source": "PPPoE",
            "mode": context.network_mode,
            "active_count": len(active_codes),
            "formula": "flat mode: PPPoE circuits point directly to router root" if flat_parent else "flat mode: PPPoE circuits use blank Parent Node",
        }
    elif per_plan_node:
        generic = ppp_flat_node_name(router)
        if generic in children:
            del children[generic]
            updated = True
        desired = set(plan_totals)
        stale = [n for n in list(children) if n.endswith(f"-{router_name}") and n not in desired and not n.startswith(("DHCP-", "HS-", "PLAN-DHCP-"))]
        for n in stale:
            del children[n]
            updated = True
        for plan_node, totals in plan_totals.items():
            df, uf = factor_for_profile(str(totals["profile"]), router.get("pppoe", {}).get("factor_rules", []))
            final_rx = float(totals["rx"]) * df
            final_tx = float(totals["tx"]) * uf
            new_node = make_node(final_rx, final_tx, router.get("pppoe", {}).get("node_type", "plan"))
            context.node_math[plan_node] = {
                "source": "PPPoE",
                "mode": "per_plan",
                "profile": str(totals["profile"]),
                "active_count": int(totals["count"]),
                "raw_download_mbps": round(float(totals["rx"]), 3),
                "raw_upload_mbps": round(float(totals["tx"]), 3),
                "download_factor": df,
                "upload_factor": uf,
                "final_download_mbps": new_node["downloadBandwidthMbps"],
                "final_upload_mbps": new_node["uploadBandwidthMbps"],
                "formula": f"{int(totals['count'])} active users, sum {round(float(totals['rx']),3)} Mbps × {df} = {new_node['downloadBandwidthMbps']} Mbps",
            }
            if children.get(plan_node) != new_node:
                children[plan_node] = new_node
                updated = True
    else:
        stale = [n for n in list(children) if n.endswith(f"-{router_name}") and not n.startswith(("DHCP-", "PPP-", "HS-", "PLAN-DHCP-"))]
        for n in stale:
            del children[n]
            updated = True
        factor = float(router.get("pppoe", {}).get("flat_aggregate_factor", 0.3))
        node_name = ppp_flat_node_name(router)
        capped_rx = min(flat_total_rx * factor, float(router.get("root_download_mbps", 115)))
        capped_tx = min(flat_total_tx * factor, float(router.get("root_upload_mbps", 115)))
        new_node = make_node(capped_rx, capped_tx, router.get("pppoe", {}).get("node_type", "plan"))
        context.node_math[node_name] = {
            "source": "PPPoE",
            "mode": "flat",
            "active_count": len(active_codes),
            "raw_download_mbps": round(flat_total_rx, 3),
            "raw_upload_mbps": round(flat_total_tx, 3),
            "download_factor": factor,
            "upload_factor": factor,
            "final_download_mbps": new_node["downloadBandwidthMbps"],
            "final_upload_mbps": new_node["uploadBandwidthMbps"],
            "formula": f"sum {round(flat_total_rx,3)} Mbps × {factor}, capped by root = {new_node['downloadBandwidthMbps']} Mbps",
        }
        if children.get(node_name) != new_node:
            children[node_name] = new_node
            updated = True

    context.counts["pppoe"] += len(active_codes)
    context.add_source_codes("PPP", active_codes)
    return active_codes, updated
