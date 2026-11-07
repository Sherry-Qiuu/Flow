"""T10 backup, restore and daily backup loop."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_KEEP = 7
DEFAULT_HOUR = 3


def backup_database(
    db_path: str | Path,
    *,
    backup_dir: str | Path | None = None,
    keep: int = DEFAULT_KEEP,
) -> Path:
    source_path = Path(db_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target_dir = (
        Path(backup_dir)
        if backup_dir is not None
        else source_path.parent / "backup"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = target_dir / f"flow-{stamp}.db"
    with closing(sqlite3.connect(str(source_path))) as source:
        with closing(sqlite3.connect(str(target))) as destination:
            source.backup(destination)
    _trim_backups(target_dir, keep)
    return target


def restore_database(
    backup_path: str | Path,
    db_path: str | Path,
) -> Path:
    source_path = Path(backup_path)
    target_path = Path(db_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not _is_valid_sqlite(source_path):
        raise RuntimeError(f"backup is not a valid SQLite file: {source_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".restore.tmp")
    with closing(sqlite3.connect(str(source_path))) as source:
        with closing(sqlite3.connect(str(temp_path))) as destination:
            source.backup(destination)
    os.replace(temp_path, target_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{target_path}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    return target_path


def latest_backup(backup_dir: str | Path) -> Path | None:
    backups = sorted(Path(backup_dir).glob("flow-*.db"))
    return backups[-1] if backups else None


def list_backups(backup_dir: str | Path) -> list[Path]:
    return sorted(Path(backup_dir).glob("flow-*.db"))


def _trim_backups(backup_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    backups = sorted(backup_dir.glob("flow-*.db"))
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            logger.warning("could not remove old backup %s", old)


def _is_valid_sqlite(path: Path) -> bool:
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")
    except sqlite3.DatabaseError:
        return False


class DailyBackup:
    """Small background loop that backs up at the configured local hour."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        backup_dir: str | Path | None = None,
        keep: int = DEFAULT_KEEP,
        hour: int = DEFAULT_HOUR,
    ) -> None:
        self.db_path = Path(db_path)
        self.backup_dir = (
            Path(backup_dir)
            if backup_dir is not None
            else self.db_path.parent / "backup"
        )
        self.keep = keep
        self.hour = max(0, min(23, int(hour)))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_backup_at: datetime | None = None
        self.last_error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="flow-daily-backup",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def backup_now(self) -> Path:
        path = backup_database(
            self.db_path,
            backup_dir=self.backup_dir,
            keep=self.keep,
        )
        self.last_backup_at = datetime.now()
        self.last_error = ""
        return path

    def _run(self) -> None:
        while not self._stop.is_set():
            delay = _seconds_until_next(self.hour)
            if self._stop.wait(delay):
                return
            try:
                self.backup_now()
                logger.info("daily backup complete: %s", self.backup_dir)
            except Exception as exc:  # pragma: no cover - disk boundary
                self.last_error = str(exc)
                logger.exception("daily backup failed")


def _seconds_until_next(hour: int, now: datetime | None = None) -> float:
    current = now or datetime.now()
    target = current.replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += timedelta(days=1)
    return max(1.0, (target - current).total_seconds())
