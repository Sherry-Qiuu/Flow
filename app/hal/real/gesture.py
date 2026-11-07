"""PAJ7620U2 gesture sensor adapter (T09)."""

from __future__ import annotations

import logging
import platform
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hal.contracts import DeviceStatus, Gesture

logger = logging.getLogger(__name__)

PAJ7620_CODES: dict[int, str] = {
    0x01: "up",
    0x02: "down",
    0x04: "left",
    0x08: "right",
    0x10: "forward",
    0x20: "backward",
    0x40: "cw",
    0x80: "ccw",
    0x100: "wave",
}


def map_code(code: Any) -> str | None:
    try:
        return PAJ7620_CODES.get(int(code))
    except (TypeError, ValueError):
        return None


def _read_part_id() -> int:
    try:
        from smbus2 import SMBus
    except ImportError:
        try:
            from smbus import SMBus  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError("smbus/smbus2 is not installed") from exc
    bus = SMBus(1)
    try:
        return int(bus.read_byte_data(0x73, 0x00))
    finally:
        bus.close()


class RealGesture(Gesture):
    name = "gesture"

    def __init__(self) -> None:
        super().__init__()
        self._sensor: Any = None
        self._callback: Callable[[str], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fault = ""

    def probe(self) -> DeviceStatus:
        if platform.system() != "Linux":
            return DeviceStatus.missing("PAJ7620 requires Linux I2C")
        if not Path("/dev/i2c-1").exists():
            return DeviceStatus.missing("/dev/i2c-1 is not available")
        try:
            import paj7620  # noqa: F401
        except ImportError:
            return DeviceStatus.missing(
                "paj7620 is not installed (pip install paj7620)"
            )
        try:
            part_id = _read_part_id()
        except Exception as exc:
            return DeviceStatus.missing(f"PAJ7620 not responding: {exc}")
        if part_id != 0x20:
            return DeviceStatus.missing(
                f"PAJ7620 part id 0x{part_id:02X}, expected 0x20"
            )
        return DeviceStatus.ok("PAJ7620 on I2C1 address 0x73")

    def open(self) -> DeviceStatus:
        if self._opened and self._sensor is not None:
            return DeviceStatus.ok("PAJ7620 opened")
        status = self.probe()
        if not status.available:
            return status
        try:
            from paj7620 import PAJ7620U2

            self._sensor = PAJ7620U2(bus=1, address=0x73)
            self._opened = True
            self._fault = ""
            return DeviceStatus.ok("PAJ7620 opened")
        except Exception as exc:
            self._opened = False
            self._fault = str(exc)
            return DeviceStatus.error(f"PAJ7620 open failed: {exc}")

    def close(self) -> None:
        self.stop()
        self._sensor = None
        self._opened = False

    def health(self) -> DeviceStatus:
        if self._fault:
            return DeviceStatus.error(self._fault)
        if (
            self._opened
            and self._thread is not None
            and self._thread.is_alive()
        ):
            return DeviceStatus.ok("PAJ7620 polling")
        return self.probe()

    def start(self, on_gesture: Callable[[str], None]) -> DeviceStatus:
        if not callable(on_gesture):
            raise TypeError("on_gesture must be callable")
        if not self._opened:
            status = self.open()
            if not status.available:
                return status
        if self._thread is not None and self._thread.is_alive():
            return DeviceStatus.ok("PAJ7620 already polling")
        self._callback = on_gesture
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="flow-paj7620",
            daemon=True,
        )
        self._thread.start()
        return DeviceStatus.ok("PAJ7620 polling")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._callback = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                code = self._sensor.get_gesture() if self._sensor else 0
            except Exception as exc:
                self._fault = f"PAJ7620 read failed: {exc}"
                logger.exception("PAJ7620 read failed")
                break
            name = map_code(code)
            callback = self._callback
            if name is not None and callback is not None:
                try:
                    callback(name)
                except Exception:  # pragma: no cover - upper boundary
                    logger.exception("gesture handler failed")
            time.sleep(0.05)
