"""Presence, approach/leave and phone placement detection."""

from __future__ import annotations

import time
from dataclasses import dataclass

from gesture.detector import GestureEvent


@dataclass(frozen=True)
class PresenceState:
    enabled: bool = True
    near: bool = False
    present: bool | None = None
    distance_cm: float | None = None
    last_event: str | None = None


class PresenceDetector:
    """Distance threshold state machine plus phone edge detection."""

    def __init__(
        self,
        *,
        approach_cm: float = 60.0,
        leave_cm: float = 300.0,
        leave_hold_s: float = 60.0,
        enabled: bool = True,
    ) -> None:
        if leave_cm <= approach_cm:
            raise ValueError("leave_cm must be greater than approach_cm")
        if leave_hold_s < 0:
            raise ValueError("leave_hold_s must be non-negative")
        self.approach_cm = approach_cm
        self.leave_cm = leave_cm
        self.leave_hold_s = leave_hold_s
        self.enabled = enabled
        self._near = False
        self._leave_since: float | None = None
        self._phone: bool | None = None
        self._last_distance: float | None = None
        self._last_event: str | None = None

    def reset(self) -> None:
        self._near = False
        self._leave_since = None
        self._phone = None
        self._last_distance = None
        self._last_event = None

    def update(
        self,
        distance_cm: float | None,
        now: float | None = None,
    ) -> GestureEvent | None:
        timestamp = time.monotonic() if now is None else now
        if not self.enabled or distance_cm is None:
            return None
        distance = max(0.0, float(distance_cm))
        self._last_distance = distance
        if distance <= self.approach_cm:
            self._leave_since = None
            if not self._near:
                self._near = True
                return self._event("approach", "wake", timestamp)
            return None
        if distance < self.leave_cm:
            self._leave_since = None
            return None
        if not self._near:
            return None
        if self._leave_since is None:
            self._leave_since = timestamp
        if timestamp - self._leave_since >= self.leave_hold_s:
            self._near = False
            self._leave_since = None
            return self._event("leave", "rest", timestamp)
        return None

    def update_phone(
        self,
        present: bool,
        now: float | None = None,
    ) -> GestureEvent | None:
        timestamp = time.monotonic() if now is None else now
        if not self.enabled:
            return None
        previous = self._phone
        self._phone = bool(present)
        if previous is None:
            return None
        if previous is False and present:
            return self._event("phone_place", "phone_place", timestamp)
        if previous is True and not present:
            return self._event("phone_take", "phone_take", timestamp)
        return None

    def seed_phone(self, present: bool) -> None:
        self._phone = bool(present)

    def state(self) -> PresenceState:
        return PresenceState(
            enabled=self.enabled,
            near=self._near,
            present=self._phone,
            distance_cm=self._last_distance,
            last_event=self._last_event,
        )

    def _event(
        self,
        kind: str,
        action: str,
        timestamp: float,
    ) -> GestureEvent:
        self._last_event = kind
        return GestureEvent(
            type=kind,
            action=action,
            confidence=0.9,
            timestamp=timestamp,
            source="presence",
        )
