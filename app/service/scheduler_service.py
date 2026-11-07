"""T15 scheduler service adapter for the T03 lifecycle."""

from __future__ import annotations

from typing import Any

from data.repositories import ReminderRepository
from scheduler.engine import ReminderScheduler
from service.config import SchedulerSettings
from service.status import ServiceStatus


class SchedulerService:
    def __init__(
        self,
        settings: SchedulerSettings,
        repo: ReminderRepository | None = None,
        *,
        publisher: Any = None,
        say: Any = None,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.publisher = publisher
        self.say = say
        self._scheduler: ReminderScheduler | None = None

    def start(self) -> ServiceStatus:
        if not self.settings.enabled:
            return ServiceStatus.disabled(
                "scheduler",
                "reminders disabled by config",
            )
        if self.repo is None:
            return ServiceStatus.error(
                "scheduler",
                "reminder repository is not available",
            )
        self._scheduler = ReminderScheduler(
            self.repo,
            publisher=self.publisher,
            say=self.say,
        )
        health = self._scheduler.start()
        if not health.healthy:
            return ServiceStatus.error("scheduler", health.detail)
        return ServiceStatus.ok("scheduler", health.detail)

    def health(self) -> ServiceStatus:
        if not self.settings.enabled:
            return ServiceStatus.disabled(
                "scheduler",
                "reminders disabled by config",
            )
        if self._scheduler is None:
            return ServiceStatus.error("scheduler", "scheduler not started")
        health = self._scheduler.health()
        if health.healthy:
            return ServiceStatus.ok("scheduler", health.detail)
        return ServiceStatus.error("scheduler", health.detail)

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None

    def snapshot(self) -> dict[str, object]:
        if self._scheduler is None:
            return {"enabled": self.settings.enabled, "running": False}
        return {
            "enabled": self.settings.enabled,
            **self._scheduler.snapshot(),
        }

    @property
    def enabled(self) -> bool:
        return self.settings.enabled and self._scheduler is not None

    def create_from_text(self, text: str) -> str:
        if self._scheduler is None:
            raise RuntimeError("scheduler is not running")
        return self._scheduler.create_from_text(text)

    def create(self, spec) -> str:
        if self._scheduler is None:
            raise RuntimeError("scheduler is not running")
        return self._scheduler.create(spec)

    def upcoming(self, hours: int = 24) -> list[dict]:
        if self._scheduler is None:
            return []
        return self._scheduler.upcoming(hours)
