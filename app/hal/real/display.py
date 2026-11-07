"""Backlight-based display control for the Raspberry Pi build."""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path

from hal.contracts import DeviceStatus, Display

logger = logging.getLogger(__name__)


class RealDisplay(Display):
    """Control a Linux backlight device.

    The Chromium kiosk renders the actual UI. The HAL only owns the
    panel backlight and keeps the latest face/text in memory so other
    services can inspect it.
    """

    name = "display"

    def __init__(self) -> None:
        super().__init__()
        self._brightness = 0.8
        self._face = "neutral"
        self._text = ""
        self._backlight: Path | None = None
        self._max_brightness = 1

    @property
    def is_open(self) -> bool:
        return self._opened

    def _find_backlight(self) -> Path | None:
        paths = sorted(glob.glob("/sys/class/backlight/*/brightness"))
        return Path(paths[0]) if paths else None

    def probe(self) -> DeviceStatus:
        path = self._find_backlight()
        if path is None:
            return DeviceStatus.missing("no /sys/class/backlight device")
        if not os.access(path, os.W_OK):
            return DeviceStatus.error(f"backlight is not writable: {path}")
        return DeviceStatus.ok(f"backlight {path.parent.name}")

    def open(self) -> DeviceStatus:
        status = self.probe()
        if not status.available:
            return status
        path = self._find_backlight()
        assert path is not None
        max_path = path.parent / "max_brightness"
        try:
            if max_path.exists():
                self._max_brightness = max(
                    1,
                    int(max_path.read_text().strip()),
                )
            current = int(path.read_text().strip())
            self._brightness = min(1.0, current / self._max_brightness)
            self._backlight = path
            self._opened = True
        except OSError as exc:
            self._opened = False
            return DeviceStatus.error(f"cannot read backlight: {exc}")
        return status

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def show_face(self, emotion: str) -> None:
        self._face = emotion or "neutral"

    def show_text(self, text: str) -> None:
        self._text = text or ""

    def clear(self) -> None:
        self._face = "neutral"
        self._text = ""

    def set_brightness(self, value: float) -> None:
        self._brightness = max(0.0, min(1.0, float(value)))
        if not self._opened or self._backlight is None:
            return
        raw = max(0, int(round(self._brightness * self._max_brightness)))
        try:
            self._backlight.write_text(f"{raw}\n")
        except OSError:
            logger.exception("failed to write backlight brightness")
