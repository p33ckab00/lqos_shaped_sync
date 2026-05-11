import time
from collectors.mikrotik_client import read_resource
from builders.circuit_rows import create_new_entry, update_entry_values, calculate_user_min_max
from builders.node_tree import dhcp_node_name, make_node
from parsers.speed_resolver import resolve_dhcp_speed
from parsers.identity import build_dhcp_code, clean_mac
from validators.duplicate_checker import check_duplicate_ip
from rules.network_mode import parent_for_flat_mode
from engine.collector_cache import stable_hash, get_source, set_source

DHCP_LEASE_FIELDS = ["server", "mac-address", "active-address", "address", "host-name", "comment", "status", "disabled", "dynamic"]
DHCP_SERVER_FIELDS = ["name", "comment"]


def _cache_key(router_name: str, suffix: str) -> str:
    return f"{router_name}:dhcp:{suffix}"


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


def _lease_included(lease: dict, server_name: str, lease_mode: str) -> bool:
    if lease.get("server") != server_name:
        return False
    if not lease.get("mac-address"):
        return False
    ip = lease.get("active-address") or lease.get("address")
    if not ip:
        return False
    if str(lease.get("disabled", "false")).lower() == "true":
        return False
    if lease_mode == "strict":
        return str(lease.get("status", "")).lower() == "bound" and bool(lease.get("active-address"))
    return True


def process_dhcp_leases(api, router: dict, context):
    dhcp_cfg = router.get("dhcp", {})
    if not dhcp_cfg.get("enabled", False):
        return set(), False
    cfg = context.config
    defaults = cfg["defaults"]
    collector_cfg = cfg.get("collector", {}).get("dhcp", {})
    lease_mode = str(collector_cfg.get("lease_mode", "permissive")).lower()
    if lease_mode not in {"permissive", "strict"}:
        lease_mode = "permissive"
    router_name = router["name"]
    flat_parent = parent_for_flat_mode(cfg, router_name)
    hierarchy_mode = flat_parent is None
    router_node = context.router_nodes.get(router_name) or context.network_config.get(router_name, {})
    children = router_node.get("children", {}) if hierarchy_mode else {}
    servers = dhcp_cfg.get("servers", [])
    updated = False
    active_codes = set()
    desired_nodes = set()

    t = time.perf_counter()
    all_leases = read_resource(api, "/ip/dhcp-server/lease", cfg, DHCP_LEASE_FIELDS)
    leases_read_ms = round((time.perf_counter() - t) * 1000, 3)
    t = time.perf_counter()
    server_rows = read_resource(api, "/ip/dhcp-server", cfg, DHCP_SERVER_FIELDS)
    servers_read_ms = round((time.perf_counter() - t) * 1000, 3)
    _record_source_hash(context, _cache_key(router_name, "leases"), all_leases)
    _record_source_hash(context, _cache_key(router_name, "servers"), server_rows)
    server_meta_by_name = {str(s.get("name", "")).strip(): s for s in server_rows if s.get("name")}

    skipped = 0
    parse_t = time.perf_counter()
    for server_cfg in servers:
        if not server_cfg.get("enabled", True):
            continue
        server_name = server_cfg.get("name")
        if not server_name:
            continue
        mode = str(server_cfg.get("mode", "per_site")).lower()
        dl_factor = float(server_cfg.get("download_factor", 0.5))
        ul_factor = float(server_cfg.get("upload_factor", 0.5))
        server_leases = [lease for lease in all_leases if _lease_included(lease, server_name, lease_mode)]
        skipped += len([lease for lease in all_leases if lease.get("server") == server_name]) - len(server_leases)
        resolved = resolve_dhcp_speed(server_cfg, server_meta_by_name.get(server_name, {}), defaults)
        per_down, per_up = resolved.download_mbps, resolved.upload_mbps
        context.count_speed_source(resolved.source)

        if mode == "per_site":
            node_name = dhcp_node_name(router, server_cfg)
            parent_node = node_name if hierarchy_mode else flat_parent
            if hierarchy_mode:
                desired_nodes.add(node_name)
            for lease in server_leases:
                mac = str(lease.get("mac-address", "")).strip()
                ip = str(lease.get("active-address") or lease.get("address") or "").strip()
                hostname = str(lease.get("host-name", "")).strip()
                code = build_dhcp_code(hostname, mac)
                device_name = hostname or clean_mac(mac)
                active_codes.add(code)
                if code not in context.existing_data:
                    if ip and check_duplicate_ip(context.existing_data, ip, code, context):
                        continue
                    context.existing_data[code] = create_new_entry(code, device_name, defaults.get("id_length", 8), mac=mac, ipv4=ip, comment="DHCP")
                    updated = True
                rx_min, tx_min, rx_max, tx_max = calculate_user_min_max(per_down, per_up, float(defaults.get("min_rate_percentage", 0.5)))
                if update_entry_values(context.existing_data[code], {"Parent Node": parent_node, "MAC": mac, "IPv4": ip, "Download Min Mbps": rx_min, "Upload Min Mbps": tx_min, "Download Max Mbps": rx_max, "Upload Max Mbps": tx_max, "Comment": hostname if hostname else "DHCP"}):
                    updated = True
                context.meta[code] = {"source_type": "DHCP", "router": router_name, "server": server_name, "base_rx": per_down, "base_tx": per_up, "speed_source": resolved.source, "speed_raw_value": resolved.raw_value, "speed_priority": resolved.priority}
            if hierarchy_mode and server_leases:
                final_rx = len(server_leases) * per_down * dl_factor
                final_tx = len(server_leases) * per_up * ul_factor
                new_node = make_node(final_rx, final_tx, server_cfg.get("node_type", "site"))
                context.node_math[node_name] = {
                    "source": "DHCP",
                    "mode": "per_site",
                    "server": server_name,
                    "active_count": len(server_leases),
                    "per_client_download_mbps": per_down,
                    "per_client_upload_mbps": per_up,
                    "speed_source": resolved.source,
                    "speed_raw_value": resolved.raw_value,
                    "download_factor": dl_factor,
                    "upload_factor": ul_factor,
                    "final_download_mbps": new_node["downloadBandwidthMbps"],
                    "final_upload_mbps": new_node["uploadBandwidthMbps"],
                    "formula": f"{len(server_leases)} leases × {per_down} Mbps × {dl_factor} = {new_node['downloadBandwidthMbps']} Mbps",
                }
                if children.get(node_name) != new_node:
                    children[node_name] = new_node
                    updated = True
            elif hierarchy_mode and node_name in children:
                del children[node_name]
                updated = True
        elif mode == "per_plan":
            # Per-plan mode is retained for compatibility, but DHCP dynamic
            # leases usually do not carry comments. The server-level resolver is
            # therefore used to create a stable plan node for all leases on this
            # DHCP server.
            plan_label = f"{int(per_down)}M" if per_down == per_up else f"{int(per_down)}M-{int(per_up)}M"
            node_name = dhcp_node_name(router, {**server_cfg, "node_name": server_cfg.get("node_name", "PLAN-DHCP-{plan}-{router}")}, plan_label=plan_label)
            parent_node = node_name if hierarchy_mode else flat_parent
            if hierarchy_mode:
                desired_nodes.add(node_name)
            plan_total_rx = 0.0
            plan_total_tx = 0.0
            plan_count = 0
            for lease in server_leases:
                mac = str(lease.get("mac-address", "")).strip()
                ip = str(lease.get("active-address") or lease.get("address") or "").strip()
                hostname = str(lease.get("host-name", "")).strip()
                code = build_dhcp_code(hostname, mac)
                device_name = hostname or clean_mac(mac)
                active_codes.add(code)
                plan_total_rx += per_down
                plan_total_tx += per_up
                plan_count += 1
                if code not in context.existing_data:
                    if ip and check_duplicate_ip(context.existing_data, ip, code, context):
                        continue
                    context.existing_data[code] = create_new_entry(code, device_name, defaults.get("id_length", 8), mac=mac, ipv4=ip, comment="DHCP")
                    updated = True
                rx_min, tx_min, rx_max, tx_max = calculate_user_min_max(per_down, per_up, float(defaults.get("min_rate_percentage", 0.5)))
                if update_entry_values(context.existing_data[code], {"Parent Node": parent_node, "MAC": mac, "IPv4": ip, "Download Min Mbps": rx_min, "Upload Min Mbps": tx_min, "Download Max Mbps": rx_max, "Upload Max Mbps": tx_max, "Comment": hostname if hostname else "DHCP"}):
                    updated = True
                context.meta[code] = {"source_type": "DHCP", "router": router_name, "server": server_name, "base_rx": per_down, "base_tx": per_up, "speed_source": resolved.source, "speed_raw_value": resolved.raw_value, "speed_priority": resolved.priority}
            if hierarchy_mode and plan_count:
                final_rx = plan_total_rx * dl_factor
                final_tx = plan_total_tx * ul_factor
                new_node = make_node(final_rx, final_tx, "plan")
                context.node_math[node_name] = {
                    "source": "DHCP",
                    "mode": "per_plan",
                    "active_count": int(plan_count),
                    "raw_download_mbps": round(float(plan_total_rx), 3),
                    "raw_upload_mbps": round(float(plan_total_tx), 3),
                    "speed_source": resolved.source,
                    "speed_raw_value": resolved.raw_value,
                    "download_factor": dl_factor,
                    "upload_factor": ul_factor,
                    "final_download_mbps": new_node["downloadBandwidthMbps"],
                    "final_upload_mbps": new_node["uploadBandwidthMbps"],
                    "formula": f"sum {round(float(plan_total_rx),3)} Mbps × {dl_factor} = {new_node['downloadBandwidthMbps']} Mbps",
                }
                if children.get(node_name) != new_node:
                    children[node_name] = new_node
                    updated = True

    parse_ms = round((time.perf_counter() - parse_t) * 1000, 3)
    if hierarchy_mode:
        stale_nodes = [n for n in list(children.keys()) if (n.startswith("DHCP-") or n.startswith("PLAN-DHCP-")) and n.endswith(f"-{router_name}") and n not in desired_nodes]
        for n in stale_nodes:
            del children[n]
            updated = True
    else:
        context.node_math[f"DHCP-flat-{router_name}"] = {
            "source": "DHCP",
            "mode": context.network_mode,
            "active_count": len(active_codes),
            "formula": "flat mode: DHCP circuits point directly to router root" if flat_parent else "flat mode: DHCP circuits use blank Parent Node",
        }
    context.collector_metrics[f"{router_name}.dhcp"] = {
        "source": "DHCP",
        "servers_configured": len(servers),
        "servers_enabled": len([s for s in servers if s.get("enabled", True)]),
        "leases_scanned": len(all_leases),
        "valid_leases": len(active_codes),
        "skipped_leases": max(0, skipped),
        "generated_rows": len(active_codes),
        "lease_mode": lease_mode,
        "read_leases_ms": leases_read_ms,
        "read_servers_ms": servers_read_ms,
        "parse_ms": parse_ms,
    }
    context.counts["dhcp"] += len(active_codes)
    context.add_source_codes("DHCP", active_codes)
    return active_codes, updated
