"""Real gesture adapter placeholder.

Gesture and presence recognition are implemented in T09. Until then the
HAL exposes a missing device instead of pretending to work.
"""

from __future__ import annotations

from collections.abc import Callable

from hal.contracts import DeviceStatus, Gesture


class RealGesture(Gesture):
    name = "gesture"

    def __init__(self) -> None:
        super().__init__()

    @property
    def is_open(self) -> bool:
        return self._opened

    def probe(self) -> DeviceStatus:
        return DeviceStatus.missing(
            "gesture sensor is delivered by T09"
        )

    def open(self) -> DeviceStatus:
        self._opened = False
        return self.probe()

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def start(self, on_gesture: Callable[[str], None]) -> DeviceStatus:
        del on_gesture
        return self.probe()

    def stop(self) -> None:
        return None
