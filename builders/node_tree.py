from builders.circuit_rows import safe_int_mbps
from parsers.profile import parse_speed_from_profile_name
from parsers.identity import render_template

def factor_for_profile(profile_name: str, factor_rules: list[dict]):
    parsed = parse_speed_from_profile_name(profile_name)
    if not parsed:
        return 1.0, 1.0
    speed = parsed[0]
    for rule in sorted(factor_rules or [], key=lambda r: float(r.get("max_plan_mbps", 999999))):
        if speed <= float(rule.get("max_plan_mbps", 999999)):
            return float(rule.get("download_factor", 1.0)), float(rule.get("upload_factor", 1.0))
    return 1.0, 1.0

def ppp_plan_node_name(router, profile_name):
    return render_template(router.get("pppoe", {}).get("plan_node_name", "{profile}-{router}"), profile=profile_name, router=router["name"])

def ppp_flat_node_name(router):
    return render_template(router.get("pppoe", {}).get("flat_node_name", "PPP-{router}"), router=router["name"])

def dhcp_node_name(router, server_cfg, plan_label=None):
    tpl = server_cfg.get("node_name") or ("PLAN-DHCP-{plan}-{router}" if plan_label else "DHCP-{server}-{router}")
    return render_template(tpl, server=server_cfg.get("name"), router=router["name"], plan=plan_label or "")

def hotspot_node_name(router):
    return render_template(router.get("hotspot", {}).get("node_name", "HS-{router}"), router=router["name"])

def make_node(download, upload, node_type="site"):
    return {"downloadBandwidthMbps": safe_int_mbps(download), "uploadBandwidthMbps": safe_int_mbps(upload), "type": node_type, "children": {}}
