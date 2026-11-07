"""SQLite database bootstrap and health for T10."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from data.backup import latest_backup, restore_database
from data.migrate import current_version, migrate

DEFAULT_USER_ID = "u_default"


@dataclass(frozen=True)
class DataHealth:
    ok: bool
    detail: str
    schema_version: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "detail": self.detail,
            "schema_version": self.schema_version,
        }


class FlowDatabase:
    def __init__(
        self,
        path: str | Path,
        *,
        backup_dir: str | Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.backup_dir = (
            Path(backup_dir)
            if backup_dir is not None
            else self.path.parent / "backup"
        )
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._last_error = ""

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("database is not started")
        return self._connection

    def start(self) -> DataHealth:
        with self._lock:
            if self._connection is not None:
                return self.health()
            try:
                return self._start_once()
            except Exception as exc:
                self._last_error = str(exc)
                backup = latest_backup(self.backup_dir)
                if backup is None:
                    return DataHealth(False, self._last_error)
                try:
                    restore_database(backup, self.path)
                    health = self._start_once()
                    self._last_error = (
                        f"recovered from backup {backup.name}"
                    )
                    return health
                except Exception as restore_error:
                    self._last_error = (
                        f"{self._last_error}; restore failed: "
                        f"{restore_error}"
                    )
                    return DataHealth(False, self._last_error)

    def _start_once(self) -> DataHealth:
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path),
                timeout=5.0,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            migrate(
                connection,
                db_path=self.path,
                backup_dir=self.backup_dir,
            )
            self._connection = connection
            connection = None
            self._last_error = ""
            return self.health()
        finally:
            if connection is not None:
                connection.close()

    def health(self) -> DataHealth:
        with self._lock:
            if self._connection is None:
                return DataHealth(
                    False,
                    self._last_error or "database is not started",
                )
            try:
                self._connection.execute("SELECT 1").fetchone()
                version = current_version(self._connection)
                return DataHealth(
                    True,
                    f"sqlite at {self.path} (schema v{version})",
                    version,
                )
            except Exception as exc:
                self._last_error = str(exc)
                return DataHealth(False, self._last_error)

    def ensure_default_user(self) -> None:
        ensure_user(self.connection, DEFAULT_USER_ID, "Flow")

    def backup_now(self) -> Path:
        from data.backup import backup_database

        return backup_database(
            self.path,
            backup_dir=self.backup_dir,
        )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


def ensure_user(
    connection: sqlite3.Connection,
    user_id: str,
    name: str,
    nickname: str = "",
) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO users "
        "(id, name, nickname, created_at, settings_json) "
        "VALUES (?, ?, ?, ?, '{}')",
        (user_id, name, nickname, _utc_now()),
    )
    connection.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
