"""Gesture service: HAL callback -> detector -> bus event."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from bus import topics
from hal.contracts import EventPublisher, Gesture, PhoneStand
from gesture.config import GestureSettings
from gesture.detector import GestureDetector, GestureEvent
from gesture.presence import PresenceDetector

logger = logging.getLogger(__name__)


class EventSubscriber(Protocol):
    def subscribe(
        self,
        topic: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> Callable[[], None]:
        ...


@dataclass(frozen=True)
class GestureHealth:
    state: str
    detail: str = ""
    events: int = 0

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "detail": self.detail,
            "events": self.events,
        }


class GestureService:
    """Owns the gesture sensor callback and publishes ``gesture.detected``."""

    def __init__(
        self,
        settings: GestureSettings,
        publisher: EventPublisher,
        gesture: Gesture | None = None,
        phone_stand: PhoneStand | None = None,
        subscriber: EventSubscriber | None = None,
    ) -> None:
        self.settings = settings
        self.publisher = publisher
        self.gesture = gesture
        self.phone_stand = phone_stand
        self.subscriber = subscriber or (
            publisher if hasattr(publisher, "subscribe") else None
        )
        self.detector = GestureDetector(
            window=settings.debounce_frames,
            min_votes=settings.min_votes,
            cooldown_s=settings.cooldown_s,
        )
        self.presence = PresenceDetector(
            approach_cm=settings.approach_cm,
            leave_cm=settings.leave_cm,
            leave_hold_s=settings.leave_hold_s,
            enabled=settings.enabled,
        )
        self._started = False
        self._disabled = False
        self._lock = threading.RLock()
        self._unsubscribe: Callable[[], None] | None = None
        self._event_count = 0
        self._last_event: GestureEvent | None = None
        self._last_error = ""

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> GestureHealth:
        if not self.settings.enabled:
            self._disabled = True
            self._last_error = "gesture detection disabled by config"
            return GestureHealth("disabled", self._last_error)
        if self.gesture is None:
            self._disabled = True
            self._last_error = "no gesture sensor in HAL"
            return GestureHealth("disabled", self._last_error)
        status = self.gesture.probe()
        if not status.available:
            self._disabled = True
            self._last_error = (
                f"gesture sensor unavailable: {status.detail}"
            )
            return GestureHealth("disabled", self._last_error)
        if not self.gesture.is_open:
            status = self.gesture.open()
            if not status.available:
                self._disabled = True
                self._last_error = (
                    f"gesture sensor unavailable: {status.detail}"
                )
                return GestureHealth("disabled", self._last_error)
        status = self.gesture.start(self._on_raw)
        if not status.available:
            self._disabled = True
            self._last_error = (
                f"gesture stream unavailable: {status.detail}"
            )
            return GestureHealth("disabled", self._last_error)
        if self.phone_stand is not None:
            try:
                self.presence.seed_phone(self.phone_stand.state().present)
            except Exception:
                logger.debug("phone seed failed", exc_info=True)
            if self.subscriber is not None:
                self._unsubscribe = self.subscriber.subscribe(
                    topics.PHONE_CHANGED,
                    self._on_phone,
                )
        self._started = True
        self._disabled = False
        self._last_error = ""
        return GestureHealth("ok", "gesture sensor listening")

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self.gesture is not None:
            try:
                self.gesture.stop()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("gesture stop failed")
        self._started = False
        self._disabled = True
        self._last_error = "gesture service stopped"

    def observe_distance(self, distance_cm: float | None) -> None:
        """Entry point for a future ToF/APDS9960 distance provider."""
        with self._lock:
            event = self.presence.update(distance_cm, time.monotonic())
        if event is not None:
            self._emit(event)

    def health(self) -> GestureHealth:
        if not self._started:
            if not self.settings.enabled or self._disabled:
                return GestureHealth(
                    "disabled",
                    self._last_error
                    or "gesture detection disabled",
                    self._event_count,
                )
            return GestureHealth(
                "disabled" if self.gesture is None else "error",
                self._last_error or "gesture service not started",
                self._event_count,
            )
        if self.gesture is not None:
            status = self.gesture.health()
            if not status.available:
                return GestureHealth(
                    "degraded",
                    f"gesture sensor: {status.detail}",
                    self._event_count,
                )
        return GestureHealth(
            "ok",
            "gesture sensor listening",
            self._event_count,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "enabled": self.settings.enabled,
            "started": self._started,
            "events": self._event_count,
            "last_event": (
                self._last_event.to_payload()
                if self._last_event is not None
                else None
            ),
            "presence": self.presence.state().__dict__,
        }

    def _on_raw(self, raw: str) -> None:
        with self._lock:
            event = self.detector.push_burst(raw)
        if event is not None:
            self._emit(event)

    def _on_phone(self, payload: dict[str, Any]) -> None:
        present = bool(payload.get("present", False))
        with self._lock:
            event = self.presence.update_phone(present, time.monotonic())
        if event is not None:
            self._emit(event)

    def _emit(self, event: GestureEvent) -> None:
        with self._lock:
            self._event_count += 1
            self._last_event = event
        try:
            self.publisher.publish(
                topics.GESTURE_DETECTED,
                event.to_payload(),
            )
        except Exception:  # pragma: no cover - bus boundary
            logger.exception("failed to publish gesture.detected")
        logger.info(
            "gesture.detected",
            extra={
                "event": "gesture.detected",
                "message_type": event.type,
            },
        )
