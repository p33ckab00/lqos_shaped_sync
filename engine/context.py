from dataclasses import dataclass, field
from typing import Any

@dataclass
class SyncContext:
    config: dict
    existing_data: dict
    network_config: dict
    network_mode: str = "router_children"
    router_nodes: dict[str, Any] = field(default_factory=dict)
    active_codes: set[str] = field(default_factory=set)
    active_codes_by_router: dict[str, set[str]] = field(default_factory=dict)
    active_codes_by_source: dict[str, set[str]] = field(default_factory=lambda: {"PPP": set(), "DHCP": set(), "HS": set()})
    router_success_names: set[str] = field(default_factory=set)
    source_success_by_router: dict[str, set[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"pppoe":0,"dhcp":0,"hotspot":0})
    meta: dict[str, Any] = field(default_factory=dict)
    node_math: dict[str, Any] = field(default_factory=dict)
    collector_metrics: dict[str, Any] = field(default_factory=dict)
    speed_source_counts: dict[str, int] = field(default_factory=dict)
    cache_metrics: dict[str, int] = field(default_factory=lambda: {"hits": 0, "misses": 0, "changes": 0, "writes": 0})
    cache: dict[str, Any] = field(default_factory=lambda: {"sources": {}})
    cache_path: str | None = None

    def count_speed_source(self, source: str):
        source = str(source or "unknown")
        self.speed_source_counts[source] = self.speed_source_counts.get(source, 0) + 1

    def add_source_codes(self, source: str, codes: set[str]):
        source = str(source or "").upper()
        if source == "HOTSPOT":
            source = "HS"
        self.active_codes_by_source.setdefault(source, set()).update(codes or set())
