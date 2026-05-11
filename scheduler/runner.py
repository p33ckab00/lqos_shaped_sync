import threading
from datetime import datetime, timezone, timedelta

from engine.config_loader import load_config
from engine.run_cycle import run_cycle
from engine.state import update_state
from engine.logging_utils import log_event


class LQoSyncScheduler:
    def __init__(self, config_path=None):
        self.config_path = config_path
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.current_job = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="lqosync-scheduler")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def is_running(self):
        return self.lock.locked()

    def _set_next_run(self, cfg, seconds):
        state_path = cfg["paths"].get("runtime_state", "state/runtime_state.json")
        next_run_at = (datetime.now(timezone.utc) + timedelta(seconds=int(seconds))).isoformat()
        update_state(state_path, next_run_at=next_run_at)

    def _loop(self):
        while not self.stop_event.is_set():
            cfg = load_config(self.config_path)
            state_path = cfg["paths"].get("runtime_state", "state/runtime_state.json")
            if not cfg.get("scheduler", {}).get("enabled", False):
                update_state(state_path, scheduler_enabled=False, scheduler_state="disabled", sync_running=False, next_run_at=None)
                self.stop_event.wait(5)
                continue

            update_state(state_path, scheduler_enabled=True)
            if self.lock.acquire(blocking=False):
                try:
                    res = run_cycle(mode="scheduled", config_path=self.config_path)
                    interval = cfg["scheduler"].get("active_interval_seconds", 30) if res.files_changed else cfg["scheduler"].get("idle_interval_seconds", 120)
                    update_state(state_path, scheduler_state="idle")
                except Exception as exc:
                    log_event(cfg, "error", f"Scheduler loop error: {exc}")
                    interval = cfg["scheduler"].get("error_retry_interval_seconds", 30)
                    update_state(state_path, scheduler_state="error", last_error=str(exc))
                finally:
                    self.lock.release()
            else:
                log_event(cfg, "warning", "Scheduled run skipped: sync already running")
                interval = cfg["scheduler"].get("active_interval_seconds", 30)

            self._set_next_run(cfg, interval)
            self.stop_event.wait(int(interval))

    def run_now_background(self, mode="manual"):
        if self.lock.locked():
            return False

        # Mark state immediately so the dashboard/status API reflects the
        # operator click on the next poll instead of waiting for the worker to
        # enter run_cycle().
        try:
            cfg0 = load_config(self.config_path)
            state_path0 = cfg0["paths"].get("runtime_state", "state/runtime_state.json")
            update_state(state_path0, scheduler_state="queued", sync_running=True, last_error=None)
        except Exception:
            pass

        def target():
            cfg = load_config(self.config_path)
            state_path = cfg["paths"].get("runtime_state", "state/runtime_state.json")
            if not self.lock.acquire(blocking=False):
                update_state(state_path, last_error="sync already running")
                return
            try:
                update_state(state_path, scheduler_state="running", sync_running=True, last_error=None)
                run_cycle(mode=mode, config_path=self.config_path)
            finally:
                self.lock.release()

        t = threading.Thread(target=target, daemon=True, name=f"lqosync-{mode}")
        t.start()
        return True
