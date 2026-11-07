"""Shared behavior for hardware-free mock devices."""

from __future__ import annotations

from hal.contracts import (
    Device,
    DeviceStatus,
    EventPublisher,
    NullPublisher,
)


class MockDevice(Device):
    """A device that is healthy until the test or demo withdraws it."""

    name = "mock"

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        *,
        detail: str = "mock device",
    ) -> None:
        super().__init__()
        self.publisher: EventPublisher = publisher or NullPublisher()
        self._detail = detail
        self._available = True
        self._unavailable_detail = "mock device missing"
        self._fault_detail = ""

    def probe(self) -> DeviceStatus:
        if self._fault_detail:
            return DeviceStatus.error(self._fault_detail)
        if not self._available:
            return DeviceStatus.missing(self._unavailable_detail)
        return DeviceStatus.ok(self._detail)

    def open(self) -> DeviceStatus:
        status = self.probe()
        self._opened = status.available
        return status

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def set_available(self, available: bool, detail: str = "") -> None:
        """Simulate plugging or unplugging a device."""
        self._available = available
        if detail:
            self._unavailable_detail = detail
        if not available:
            self._opened = False

    def inject_fault(self, detail: str) -> None:
        """Simulate a runtime device failure."""
        self._fault_detail = detail or "mock device error"

    def clear_fault(self) -> None:
        self._fault_detail = ""

    @property
    def available(self) -> bool:
        return self.probe().available
