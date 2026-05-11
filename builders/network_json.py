import json
from pathlib import Path

def read_network_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def render_network_json(data: dict) -> str:
    return json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False) + "\n"

def ensure_router_root(network_config: dict, router: dict) -> None:
    router_name = router["name"]
    if router_name not in network_config or not isinstance(network_config.get(router_name), dict):
        network_config[router_name] = {"children": {}}
    node = network_config[router_name]
    node["downloadBandwidthMbps"] = router.get("root_download_mbps", 115)
    node["uploadBandwidthMbps"] = router.get("root_upload_mbps", 115)
    node["type"] = router.get("root_type", "site")
    node["virtual"] = bool(router.get("root_virtual", False))
    if "children" not in node or not isinstance(node["children"], dict):
        node["children"] = {}

def count_nodes(network: dict) -> int:
    count = 0
    def visit(node):
        nonlocal count
        if isinstance(node, dict):
            count += 1
            for child in node.get("children", {}).values():
                visit(child)
    for node in (network or {}).values():
        visit(node)
    return count
