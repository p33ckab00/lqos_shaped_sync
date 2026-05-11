"""Inter-process lock for LQoSync.

This prevents duplicate sync cycles when the app is served by gunicorn,
multiple threads, or a stuck scheduled run overlaps with a manual run.
"""
from __future__ import annotations

import os
from pathlib import Path
from contextlib import AbstractContextManager

try:
    import fcntl  # Linux/Unix only; LQoSync targets Linux servers.
except Exception:  # pragma: no cover
    fcntl = None


class LockBusy(RuntimeError):
    pass


class InterProcessLock(AbstractContextManager):
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._fh = None

    def acquire(self, blocking: bool = False) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a+")
        if fcntl is None:
            # Fallback: best effort. Thread lock still protects normal operation.
            return True
        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fh.fileno(), flags)
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(str(os.getpid()))
            self._fh.flush()
            return True
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False

    def release(self):
        if self._fh is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None

    def __enter__(self):
        if not self.acquire(blocking=False):
            raise LockBusy(f"Another LQoSync cycle is already running: {self.path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
