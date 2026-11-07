"""Persist boot self-test results to the ``device_status`` table."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS device_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_status_checked_at
    ON device_status (checked_at);
"""


@dataclass(frozen=True)
class DeviceStatusRow:
    device: str
    status: str
    detail: str
    checked_at: datetime


def _project_data_dir() -> Path:
    """Use the repository's ``data/`` folder when running from source."""
    app_dir = Path(__file__).resolve().parents[1]
    project_root = app_dir.parent
    if (project_root / "app").is_dir():
        return project_root / "data"
    return Path("data")


def default_db_path(env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    explicit = values.get("FLOW_DB")
    if explicit:
        return Path(explicit)
    configured = values.get("FLOW_DATA_DIR")
    data_dir = Path(configured) if configured else _project_data_dir()
    return data_dir / "flow.db"


def write_device_status(
    rows: list[DeviceStatusRow],
    db_path: str | Path | None = None,
) -> Path:
    """Write one row per device and return the database path."""
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        (
            row.device,
            row.status,
            row.detail,
            row.checked_at.isoformat(),
        )
        for row in rows
    ]
    with closing(sqlite3.connect(str(path), timeout=5.0)) as connection:
        with connection:
            connection.executescript(SCHEMA)
            connection.executemany(
                "INSERT INTO device_status "
                "(device, status, detail, checked_at) "
                "VALUES (?, ?, ?, ?)",
                payload,
            )
    return path


def read_device_status(
    db_path: str | Path | None = None,
    *,
    limit: int = 500,
) -> list[dict[str, str | int]]:
    """Return recent rows, newest first, for diagnostics and tests."""
    path = Path(db_path) if db_path is not None else default_db_path()
    if not path.exists():
        return []
    with closing(sqlite3.connect(str(path), timeout=5.0)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, device, status, detail, checked_at "
            "FROM device_status ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
