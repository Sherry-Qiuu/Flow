"""HAL lifecycle and health adapter for the backend skeleton."""

from __future__ import annotations

from typing import Any

from hal.contracts import DeviceStatus, EventPublisher, PhoneState
from hal.factory import Hal, create_hal
from service.config import HalSettings
from service.status import ServiceStatus


class HalService:
    def __init__(
        self,
        settings: HalSettings,
        publisher: EventPublisher,
        hal: Hal | None = None,
    ) -> None:
        self.settings = settings
        self.publisher = publisher
        self._hal = hal
        self._statuses: dict[str, DeviceStatus] = {}
        self._last_error = ""

    @property
    def hal(self) -> Hal | None:
        return self._hal

    def start(self) -> ServiceStatus:
        try:
            if self._hal is None:
                self._hal = create_hal(
                    self.settings.backend,
                    self.publisher,
                )
            self._statuses = self._hal.open_all()
            unavailable = [
                name
                for name, status in self._statuses.items()
                if not status.available
            ]
            if not unavailable:
                return ServiceStatus.ok(
                    "hal",
                    f"backend={self._hal.backend}",
                )
            self._last_error = ", ".join(unavailable)
            return ServiceStatus.degraded(
                "hal",
                f"degraded: {self._last_error}",
            )
        except Exception as exc:
            self._last_error = str(exc)
            return ServiceStatus.error("hal", self._last_error)

    def health(self) -> ServiceStatus:
        if self._hal is None:
            return ServiceStatus.error(
                "hal",
                self._last_error or "HAL is not started",
            )
        try:
            statuses = self._hal.health()
        except Exception as exc:
            return ServiceStatus.error("hal", str(exc))
        unavailable = [
            name
            for name, status in statuses.items()
            if not status.available
        ]
        if unavailable:
            return ServiceStatus.degraded(
                "hal",
                f"degraded: {', '.join(unavailable)}",
            )
        return ServiceStatus.ok(
            "hal",
            f"backend={self._hal.backend}",
        )

    def stop(self) -> None:
        if self._hal is not None:
            self._hal.close()

    def device_snapshot(self) -> dict[str, Any]:
        if self._hal is None:
            return {}
        statuses = self._hal.health()
        return {
            name: status.to_dict()
            for name, status in statuses.items()
        }

    def phone_state(self) -> dict[str, Any]:
        if self._hal is None:
            return PhoneState().to_dict()
        return self._hal.phone_stand.state().to_dict()

    def faults(self) -> dict[str, dict[str, Any]]:
        if self._hal is None:
            return {}
        return {
            name: status.to_dict()
            for name, status in self._hal.faulted_devices().items()
        }
