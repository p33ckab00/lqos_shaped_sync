import json
from pathlib import Path


def read_network_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def render_network_json(data: dict) -> str:
    return json.dumps(data or {}, indent=4, sort_keys=True, ensure_ascii=False) + "\n"


def _children(node: dict) -> dict:
    if "children" not in node or not isinstance(node.get("children"), dict):
        node["children"] = {}
    return node["children"]


def find_node(network: dict, node_name: str) -> dict | None:
    """Find a node anywhere in a LibreQoS network.json tree."""
    if not node_name:
        return None
    if node_name in (network or {}):
        return network[node_name]
    for node in (network or {}).values():
        found = _find_child(node, node_name)
        if found is not None:
            return found
    return None


def _find_child(node: dict, node_name: str) -> dict | None:
    for child_name, child in (node.get("children", {}) or {}).items():
        if child_name == node_name:
            return child
        found = _find_child(child, node_name)
        if found is not None:
            return found
    return None


def _remove_node(network: dict, node_name: str) -> dict | None:
    """Remove a node from wherever it currently exists and return the node."""
    if node_name in network:
        return network.pop(node_name)
    for node in list(network.values()):
        removed = _remove_child(node, node_name)
        if removed is not None:
            return removed
    return None


def _remove_child(node: dict, node_name: str) -> dict | None:
    children = node.get("children", {}) or {}
    if node_name in children:
        return children.pop(node_name)
    for child in list(children.values()):
        removed = _remove_child(child, node_name)
        if removed is not None:
            return removed
    return None


def _default_node(download=0, upload=0, node_type="site", virtual=False) -> dict:
    node = {
        "downloadBandwidthMbps": download,
        "uploadBandwidthMbps": upload,
        "type": node_type,
        "children": {},
    }
    if virtual:
        node["virtual"] = True
    return node


def ensure_router_root(network_config: dict, router: dict) -> dict:
    """Ensure the router exists as a root-level node and return it."""
    router_name = router["name"]
    node = _remove_node(network_config, router_name) or {}
    if not isinstance(node, dict):
        node = {}
    node["downloadBandwidthMbps"] = router.get("root_download_mbps", 115)
    node["uploadBandwidthMbps"] = router.get("root_upload_mbps", 115)
    node["type"] = router.get("root_type", "site")
    node["virtual"] = bool(router.get("root_virtual", False))
    _children(node)
    network_config[router_name] = node
    return node


def ensure_parent_node(network_config: dict, parent_name: str) -> dict:
    """Ensure a parent/grouping node exists somewhere; root-level if not found."""
    node = find_node(network_config, parent_name)
    if node is not None:
        _children(node)
        return node
    node = _default_node(0, 0, "site", virtual=True)
    network_config[parent_name] = node
    return node


def ensure_router_node(network_config: dict, router: dict, allow_parent: bool = False) -> dict:
    """Ensure router node exists; optionally attach under router.parent_node.

    Deep/custom hierarchy mode uses router.parent_node to nest routers under
    upstream/core/site nodes. Normal hierarchy still places routers at root.
    """
    router_name = router["name"]
    parent_name = str(router.get("parent_node") or "").strip()
    node = _remove_node(network_config, router_name) or {}
    if not isinstance(node, dict):
        node = {}
    node["downloadBandwidthMbps"] = router.get("root_download_mbps", 115)
    node["uploadBandwidthMbps"] = router.get("root_upload_mbps", 115)
    node["type"] = router.get("root_type", "site")
    node["virtual"] = bool(router.get("root_virtual", False))
    _children(node)
    if allow_parent and parent_name and parent_name != router_name:
        parent = ensure_parent_node(network_config, parent_name)
        _children(parent)[router_name] = node
    else:
        network_config[router_name] = node
    return node


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


def flatten_nodes(network: dict) -> list[dict]:
    """Return [{name,path,type,virtual,children_count,download,upload}] for UI/validation."""
    out = []
    def walk(name, node, path):
        children = node.get("children", {}) if isinstance(node, dict) else {}
        out.append({
            "name": name,
            "path": path + [name],
            "type": (node or {}).get("type", "site") if isinstance(node, dict) else "site",
            "virtual": bool((node or {}).get("virtual", False)) if isinstance(node, dict) else False,
            "children_count": len(children or {}),
            "downloadBandwidthMbps": (node or {}).get("downloadBandwidthMbps", 0) if isinstance(node, dict) else 0,
            "uploadBandwidthMbps": (node or {}).get("uploadBandwidthMbps", 0) if isinstance(node, dict) else 0,
        })
        for child_name, child in (children or {}).items():
            walk(child_name, child, path + [name])
    for root_name, root in (network or {}).items():
        walk(root_name, root, [])
    return out
