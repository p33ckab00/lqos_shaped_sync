"""Network layout mode helpers for LQoSync.

Supported modes:
- router_children: current production hierarchy; router root with PPP/DHCP/HS child nodes.
- flat_router_root: router root only; every generated circuit points directly to the router root.
- flat_no_parent: pure flat CSV; generated circuits have blank Parent Node and network.json is empty unless preserved.
"""

VALID_NETWORK_MODES = {"router_children", "flat_router_root", "flat_no_parent"}


def mode_from_legacy_flags(flat_network: bool, no_parent: bool) -> str:
    if flat_network and no_parent:
        return "flat_no_parent"
    if flat_network and not no_parent:
        return "flat_router_root"
    return "router_children"


def legacy_flags_for_mode(mode: str) -> tuple[bool, bool]:
    if mode == "flat_no_parent":
        return True, True
    if mode == "flat_router_root":
        return True, False
    return False, False


def get_network_mode(config: dict) -> str:
    mode = config.get("network_mode")
    if isinstance(mode, str) and mode in VALID_NETWORK_MODES:
        return mode
    return mode_from_legacy_flags(bool(config.get("flat_network", False)), bool(config.get("no_parent", False)))


def normalize_network_mode(config: dict) -> str:
    mode = get_network_mode(config)
    config["network_mode"] = mode
    flat, no_parent = legacy_flags_for_mode(mode)
    config["flat_network"] = flat
    config["no_parent"] = no_parent
    config.setdefault("preserve_network_config", False)
    return mode


def is_hierarchy(config: dict) -> bool:
    return get_network_mode(config) == "router_children"


def is_flat_router_root(config: dict) -> bool:
    return get_network_mode(config) == "flat_router_root"


def is_flat_no_parent(config: dict) -> bool:
    return get_network_mode(config) == "flat_no_parent"


def parent_for_flat_mode(config: dict, router_name: str) -> str | None:
    """Return override parent for flat modes, or None if hierarchy mode should handle it."""
    mode = get_network_mode(config)
    if mode == "flat_no_parent":
        return ""
    if mode == "flat_router_root":
        return router_name
    return None


def describe_mode(mode: str) -> str:
    return {
        "router_children": "Router root with PPPoE/DHCP/Hotspot child nodes",
        "flat_router_root": "Flat network with all generated circuits under the router root",
        "flat_no_parent": "Pure flat network with blank Parent Node and no generated network.json nodes",
    }.get(mode, "Unknown")
