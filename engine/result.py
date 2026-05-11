from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

@dataclass
class SyncResult:
    mode: str = "dry_run"
    status: str = "started"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    duration_seconds: float = 0.0
    routers_processed: int = 0
    router_errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"pppoe":0,"dhcp":0,"hotspot":0,"csv_rows":0,"nodes":0})
    csv_changed: bool = False
    network_changed: bool = False
    files_changed: bool = False
    libreqos_triggered: bool = False
    libreqos_exit_code: int | None = None
    libreqos_stdout: str = ""
    libreqos_stderr: str = ""
    diff: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    node_math: dict[str, Any] = field(default_factory=dict)
    file_hashes: dict[str, str | None] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def finish(self, status="success"):
        end = datetime.now(timezone.utc)
        self.finished_at = end.isoformat()
        try:
            start = datetime.fromisoformat(self.started_at)
            self.duration_seconds = round((end - start).total_seconds(), 3)
        except Exception:
            pass
        self.status = status
        return self

    def to_dict(self):
        return asdict(self)
