"""Mock camera returning a small embedded JPEG."""

from __future__ import annotations

from hal.contracts import DeviceStatus, EventPublisher
from hal.mock.assets import MOCK_JPEG
from hal.mock.base import MockDevice


class MockCamera(MockDevice):
    name = "camera"

    def __init__(self, publisher: EventPublisher | None = None) -> None:
        super().__init__(publisher, detail="mock camera")
        self._captures = 0

    @property
    def captures(self) -> int:
        return self._captures

    def capture(self) -> bytes | None:
        if not self._opened:
            status = self.open()
            if not status.available:
                return None
        if not self.probe().available:
            return None
        self._captures += 1
        return MOCK_JPEG

    def unplug(self) -> None:
        self.set_available(False, "camera unplugged (mock)")

    def plug(self) -> None:
        self.set_available(True)

    def health(self) -> DeviceStatus:
        return self.probe()
