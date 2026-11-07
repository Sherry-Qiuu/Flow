"""Phone stand sensors: micro switch, optional charging pin, INA219."""

from __future__ import annotations

import glob
import logging
import os
import platform
import threading
from typing import Any

from bus import topics
from hal.contracts import (
    DeviceStatus,
    EventPublisher,
    NullPublisher,
    PhoneStand,
    PhoneState,
)

logger = logging.getLogger(__name__)


class RealPhoneStand(PhoneStand):
    """Read phone presence and charging state, then publish changes."""

    name = "phone_stand"

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        *,
        present_pin: int | None = None,
        charging_pin: int | None = None,
        poll_interval: float | None = None,
    ) -> None:
        super().__init__()
        self.publisher = publisher or NullPublisher()
        self.present_pin = (
            present_pin
            if present_pin is not None
            else int(os.environ.get("FLOW_PHONE_PRESENT_PIN", "17"))
        )
        charge_pin = os.environ.get("FLOW_PHONE_CHARGE_PIN", "")
        self.charging_pin = charging_pin if charging_pin is not None else (
            int(charge_pin) if charge_pin else None
        )
        poll_ms = float(os.environ.get("FLOW_PHONE_POLL_MS", "100"))
        self.poll_interval = (
            poll_interval if poll_interval is not None else poll_ms / 1000.0
        )
        self.poll_interval = max(0.01, self.poll_interval)
        self._opened = False
        self._button: Any = None
        self._charge_button: Any = None
        self._ina: Any = None
        self._state = PhoneState(
            present=False,
            charging=False,
            current_ma=0,
            distance_mm=-1,
        )
        self._last_published = self._state
        self._state_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_open(self) -> bool:
        return self._opened

    def probe(self) -> DeviceStatus:
        if platform.system() != "Linux":
            return DeviceStatus.missing("GPIO sensors require Linux")
        chips = glob.glob("/dev/gpiochip*")
        if not chips:
            return DeviceStatus.missing("no /dev/gpiochip* device")
        try:
            import gpiozero  # noqa: F401
        except ImportError:
            return DeviceStatus.missing("gpiozero is not installed")
        return DeviceStatus.ok(f"GPIO available ({chips[0]})")

    def open(self) -> DeviceStatus:
        status = self.probe()
        if not status.available:
            return status
        try:
            from gpiozero import Button

            self._button = Button(
                self.present_pin,
                pull_up=True,
                bounce_time=0.05,
            )
            if self.charging_pin is not None:
                self._charge_button = Button(
                    self.charging_pin,
                    pull_up=True,
                    bounce_time=0.05,
                )
        except Exception as exc:
            self._opened = False
            return DeviceStatus.error(f"GPIO open failed: {exc}")
        address = int(os.environ.get("FLOW_INA219_ADDR", "0x40"), 0)
        try:
            from ina219 import INA219

            self._ina = INA219(shunt_ohms=0.1, address=address)
            self._ina.configure()
        except Exception as exc:
            logger.info("INA219 unavailable, charging is inferred: %s", exc)
            self._ina = None
        with self._state_lock:
            self._state = self._read_state()
            self._last_published = self._state
        self._opened = True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._watch,
            name="flow-phone-stand",
            daemon=True,
        )
        self._thread.start()
        return DeviceStatus.ok("phone stand opened")

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        for handle in (self._button, self._charge_button):
            if handle is not None:
                try:
                    handle.close()
                except Exception:  # pragma: no cover - hardware boundary
                    logger.exception("failed to close GPIO button")
        self._button = None
        self._charge_button = None
        if self._ina is not None:
            try:
                self._ina.close()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("failed to close INA219")
            self._ina = None
        self._opened = False

    def state(self) -> PhoneState:
        with self._state_lock:
            return self._state

    def health(self) -> DeviceStatus:
        if not self._opened:
            return self.probe()
        return DeviceStatus.ok("phone stand polling")

    def _read_state(self) -> PhoneState:
        present = False
        if self._button is not None:
            present = bool(self._button.is_pressed)
        current_ma = 0
        if self._ina is not None:
            try:
                current_ma = int(round(abs(float(self._ina.current))))
            except Exception:
                logger.warning("INA219 read failed", exc_info=True)
        if self._charge_button is not None:
            charging = bool(self._charge_button.is_pressed)
        else:
            charging = present and current_ma > 50
        return PhoneState(
            present=present,
            charging=charging,
            current_ma=current_ma,
            distance_mm=-1,
        )

    def _watch(self) -> None:
        while not self._stop.wait(self.poll_interval):
            try:
                current = self._read_state()
            except Exception:
                logger.exception("phone stand read failed")
                continue
            with self._state_lock:
                self._state = current
                if current == self._last_published:
                    continue
                self._last_published = current
            try:
                self.publisher.publish(topics.PHONE_CHANGED, current.to_dict())
            except Exception:  # pragma: no cover - event bus boundary
                logger.exception("failed to publish phone.changed")
