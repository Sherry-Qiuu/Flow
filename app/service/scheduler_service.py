"""Scheduler placeholder for the T03 lifecycle.

T15 owns the real APScheduler implementation. The skeleton exposes the
same start/stop/health shape so the lifecycle order is already correct.
"""

from __future__ import annotations

from service.config import SchedulerSettings
from service.status import ServiceStatus


class SchedulerService:
    def __init__(self, settings: SchedulerSettings) -> None:
        self.settings = settings
        self._started = False

    def start(self) -> ServiceStatus:
        self._started = True
        if not self.settings.enabled:
            return ServiceStatus.disabled(
                "scheduler",
                "scheduler disabled; T15 not installed",
            )
        return ServiceStatus.degraded(
            "scheduler",
            "scheduler enabled but T15 is not installed",
        )

    def health(self) -> ServiceStatus:
        if not self.settings.enabled:
            return ServiceStatus.disabled(
                "scheduler",
                "scheduler disabled; T15 not installed",
            )
        if not self._started:
            return ServiceStatus.error("scheduler", "scheduler not started")
        return ServiceStatus.degraded(
            "scheduler",
            "scheduler skeleton; T15 not installed",
        )

    def stop(self) -> None:
        self._started = False
