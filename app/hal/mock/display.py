"""In-memory display used when no screen is attached."""

from __future__ import annotations

from typing import Any

from hal.contracts import DeviceStatus, EventPublisher
from hal.mock.base import MockDevice


class MockDisplay(MockDevice):
    name = "display"

    def __init__(self, publisher: EventPublisher | None = None) -> None:
        super().__init__(publisher, detail="mock display")
        self._face = "neutral"
        self._text = ""
        self._brightness = 0.8

    def show_face(self, emotion: str) -> None:
        self._face = emotion or "neutral"

    def show_text(self, text: str) -> None:
        self._text = text or ""

    def clear(self) -> None:
        self._face = "neutral"
        self._text = ""

    def set_brightness(self, value: float) -> None:
        self._brightness = max(0.0, min(1.0, float(value)))

    @property
    def brightness(self) -> float:
        return self._brightness

    def snapshot(self) -> dict[str, Any]:
        return {
            "face": self._face,
            "text": self._text,
            "brightness": self._brightness,
        }

    def health(self) -> DeviceStatus:
        return self.probe()
