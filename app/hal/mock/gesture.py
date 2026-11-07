"""Mock gesture sensor driven explicitly by demos and tests."""

from __future__ import annotations

import threading
from collections.abc import Callable

from hal.contracts import DeviceStatus, EventPublisher
from hal.mock.base import MockDevice


class MockGesture(MockDevice):
    name = "gesture"

    def __init__(self, publisher: EventPublisher | None = None) -> None:
        super().__init__(publisher, detail="mock gesture sensor")
        self._callback: Callable[[str], None] | None = None
        self._lock = threading.RLock()
        self._events: list[str] = []

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self._events)

    def start(self, on_gesture: Callable[[str], None]) -> DeviceStatus:
        if not callable(on_gesture):
            raise TypeError("on_gesture must be callable")
        if not self._opened:
            status = self.open()
            if not status.available:
                return status
        with self._lock:
            self._callback = on_gesture
        return DeviceStatus.ok("mock gesture sensor listening")

    def stop(self) -> None:
        with self._lock:
            self._callback = None

    def trigger(self, gesture: str) -> None:
        """Emit a gesture such as ``wave`` or ``approach``."""
        name = gesture or "unknown"
        self._events.append(name)
        callback = self._callback
        if callback is not None:
            callback(name)

    def health(self) -> DeviceStatus:
        return self.probe()
