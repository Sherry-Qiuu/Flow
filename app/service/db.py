"""T03 database lifecycle backed by the T10 data layer."""

from __future__ import annotations

from pathlib import Path

from data.database import FlowDatabase
from service.status import ServiceStatus


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._database = FlowDatabase(self.path)

    def start(self) -> ServiceStatus:
        health = self._database.start()
        if not health.ok:
            return ServiceStatus.error("db", health.detail)
        try:
            self._database.ensure_default_user()
        except Exception as exc:
            return ServiceStatus.error("db", f"default user: {exc}")
        return ServiceStatus.ok("db", health.detail)

    def health(self) -> ServiceStatus:
        health = self._database.health()
        if health.ok:
            return ServiceStatus.ok("db", health.detail)
        return ServiceStatus.error("db", health.detail)

    def stop(self) -> None:
        self._database.close()

    @property
    def connection(self):
        return self._database.connection

    @property
    def data(self) -> FlowDatabase:
        return self._database

    def backup_now(self) -> Path:
        return self._database.backup_now()
