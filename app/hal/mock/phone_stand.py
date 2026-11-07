"""Mock phone stand with a polling event stream."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import datetime, timezone

from bus import topics
from hal.contracts import DeviceStatus, EventPublisher, PhoneState
from hal.mock.base import MockDevice

logger = logging.getLogger(__name__)


class MockPhoneStand(MockDevice):
    """Simulate presence and charging sensors.

    State changes are published as ``phone.changed`` by a polling
    thread, mirroring the real sensor path. The 100 ms poll keeps the
    event well inside the 300 ms contract.
    """

    name = "phone_stand"

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        *,
        poll_interval: float = 0.1,
        initial: PhoneState | None = None,
    ) -> None:
        super().__init__(publisher, detail="mock phone stand")
        self.poll_interval = max(0.01, poll_interval)
        self._state = initial or PhoneState(
            present=False,
            charging=False,
            current_ma=0,
            distance_mm=120,
        )
        self._last_published = self._state
        self._state_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._published = 0

    @property
    def published_events(self) -> int:
        return self._published

    def state(self) -> PhoneState:
        with self._state_lock:
            return self._state

    def set_state(
        self,
        *,
        present: bool | None = None,
        charging: bool | None = None,
        current_ma: int | None = None,
        distance_mm: int | None = None,
    ) -> PhoneState:
        with self._state_lock:
            changes = {}
            if present is not None:
                changes["present"] = bool(present)
            if charging is not None:
                changes["charging"] = bool(charging)
            if current_ma is not None:
                changes["current_ma"] = int(current_ma)
            if distance_mm is not None:
                changes["distance_mm"] = int(distance_mm)
            self._state = replace(self._state, **changes)
            return self._state

    def place_phone(self, *, charging: bool = True) -> PhoneState:
        return self.set_state(
            present=True,
            charging=charging,
            current_ma=420 if charging else 0,
            distance_mm=8,
        )

    def remove_phone(self) -> PhoneState:
        return self.set_state(
            present=False,
            charging=False,
            current_ma=0,
            distance_mm=120,
        )

    def open(self) -> DeviceStatus:
        status = super().open()
        if not status.available:
            return status
        with self._state_lock:
            self._last_published = self._state
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._watch,
                name="flow-mock-phone-stand",
                daemon=True,
            )
            self._thread.start()
        return status

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        super().close()

    def _watch(self) -> None:
        while not self._stop.wait(self.poll_interval):
            if not self.probe().available:
                break
            current = self.state()
            with self._state_lock:
                if current == self._last_published:
                    continue
                self._last_published = current
            self._published += 1
            try:
                payload = current.to_dict()
                payload["at"] = datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ).replace("+00:00", "Z")
                self.publisher.publish(topics.PHONE_CHANGED, payload)
            except Exception:  # pragma: no cover - event bus boundary
                logger.exception("failed to publish phone.changed")

    def health(self) -> DeviceStatus:
        return self.probe()
