"""SQLite lifecycle and health probe.

T10 will replace this with the full DAO. T03 only needs WAL mode and a
working connection so ``/healthz`` can report the db subsystem.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from service.status import ServiceStatus


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._last_error = ""

    def start(self) -> ServiceStatus:
        with self._lock:
            if self._connection is not None:
                return ServiceStatus.ok("db", f"sqlite at {self.path}")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    str(self.path),
                    timeout=5.0,
                    check_same_thread=False,
                )
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute("SELECT 1").fetchone()
                self._connection = connection
                self._last_error = ""
                return ServiceStatus.ok("db", f"sqlite at {self.path}")
            except Exception as exc:
                self._last_error = str(exc)
                return ServiceStatus.error("db", self._last_error)

    def health(self) -> ServiceStatus:
        with self._lock:
            if self._connection is None:
                return ServiceStatus.error(
                    "db",
                    self._last_error or "database is not connected",
                )
            try:
                self._connection.execute("SELECT 1").fetchone()
                return ServiceStatus.ok("db", f"sqlite at {self.path}")
            except Exception as exc:
                self._last_error = str(exc)
                return ServiceStatus.error("db", self._last_error)

    def stop(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
