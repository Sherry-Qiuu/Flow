"""Per-connection locks: several hardware/reminder threads share one SQLite."""

from __future__ import annotations

import threading

_LOCK = threading.RLock()
_LOCKS: dict[int, threading.RLock] = {}


def get_connection_lock(connection) -> threading.RLock:
    with _LOCK:
        return _LOCKS.setdefault(id(connection), threading.RLock())
