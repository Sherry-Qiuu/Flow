"""T10 schema migration and verification."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from data.backup import backup_database

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
LATEST_SCHEMA_VERSION = 1

CORE_TABLES = (
    "users",
    "tasks",
    "subtasks",
    "plans",
    "plan_items",
    "focus_sessions",
    "reminders",
    "phone_sessions",
    "distractions",
    "reward_events",
    "companion_state",
    "device_events",
    "metrics_daily",
    "settings",
)
META_TABLES = ("device_status", "schema_version")
ALL_TABLES = CORE_TABLES + META_TABLES


@dataclass(frozen=True)
class MigrationResult:
    previous_version: int
    version: int
    applied: bool
    backup_path: str | None = None


def migrate(
    connection: sqlite3.Connection,
    *,
    db_path: str | Path | None = None,
    backup_dir: str | Path | None = None,
) -> MigrationResult:
    """Apply migrations idempotently; back up an existing database first."""
    connection.execute("PRAGMA foreign_keys=ON")
    _ensure_version_table(connection)
    previous = current_version(connection)
    if previous > LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema v{previous} is newer than app "
            f"v{LATEST_SCHEMA_VERSION}"
        )

    backup_path: str | None = None
    if (
        previous < LATEST_SCHEMA_VERSION
        and db_path is not None
        and _has_business_tables(connection)
    ):
        backup_path = str(
            backup_database(db_path, backup_dir=backup_dir)
        )

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema)
    connection.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) "
        "VALUES (?, ?)",
        (LATEST_SCHEMA_VERSION, _utc_now()),
    )
    connection.commit()
    missing = missing_tables(connection)
    if missing:
        raise RuntimeError(f"schema is incomplete: {', '.join(missing)}")
    return MigrationResult(
        previous_version=previous,
        version=LATEST_SCHEMA_VERSION,
        applied=previous < LATEST_SCHEMA_VERSION,
        backup_path=backup_path,
    )


def current_version(connection: sqlite3.Connection) -> int:
    try:
        row = connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0] or 0) if row else 0


def missing_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    present = {str(row[0]) for row in rows}
    return [table for table in ALL_TABLES if table not in present]


def _ensure_version_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    connection.commit()


def _has_business_tables(connection: sqlite3.Connection) -> bool:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    present = {str(row[0]) for row in rows}
    return any(table in present for table in CORE_TABLES)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
