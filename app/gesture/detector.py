"""Raw gesture -> semantic action with a sliding window and cooldown."""

from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass

ACTION_MAP: dict[str, str] = {
    "wave": "confirm",
    "left": "prev",
    "right": "next",
    "up": "extend",
    "down": "shorten",
    "cw": "channel_next",
    "ccw": "channel_prev",
    "forward": "finish_step",
    "backward": "skip_step",
}

ALIASES: dict[str, str] = {
    "向上": "up",
    "向下": "down",
    "向左": "left",
    "向右": "right",
    "向前": "forward",
    "向后": "backward",
    "顺时针": "cw",
    "逆时针": "ccw",
    "挥动": "wave",
    "挥手": "wave",
    "circle_cw": "cw",
    "circle_ccw": "ccw",
    "clockwise": "cw",
    "counterclockwise": "ccw",
    "counter_clockwise": "ccw",
}

KNOWN_GESTURES = tuple(ACTION_MAP)
PRESENCE_TYPES = ("approach", "leave", "phone_place", "phone_take")


@dataclass(frozen=True)
class GestureEvent:
    """One semantic gesture event."""

    type: str
    action: str
    confidence: float
    timestamp: float
    source: str = "sensor"

    def to_payload(self) -> dict[str, object]:
        return {
            "type": self.type,
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


class GestureDetector:
    """Debounce raw frames and emit one semantic event per cooldown."""

    def __init__(
        self,
        *,
        window: int = 5,
        min_votes: int = 2,
        cooldown_s: float = 1.5,
    ) -> None:
        if window < 1:
            raise ValueError("window must be positive")
        if not 1 <= min_votes <= window:
            raise ValueError("min_votes must be in 1..window")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        self.window = window
        self.min_votes = min_votes
        self.cooldown_s = cooldown_s
        self._frames: deque[str | None] = deque(maxlen=window)
        self._last_emitted: dict[str, float] = {}

    def reset(self) -> None:
        self._frames.clear()
        self._last_emitted.clear()

    def push(
        self,
        raw: str | None,
        now: float | None = None,
    ) -> GestureEvent | None:
        timestamp = time.monotonic() if now is None else now
        name = normalize_gesture(raw)
        self._frames.append(name)
        return self._evaluate(name, timestamp)

    def push_burst(
        self,
        raw: str,
        now: float | None = None,
    ) -> GestureEvent | None:
        """Fill one event-driven sensor reading into the whole window."""
        timestamp = time.monotonic() if now is None else now
        name = normalize_gesture(raw)
        for _ in range(self.window):
            self._frames.append(name)
        return self._evaluate(name, timestamp)

    def _evaluate(
        self,
        name: str | None,
        timestamp: float,
    ) -> GestureEvent | None:
        if name is None or name not in ACTION_MAP:
            return None
        votes = sum(1 for frame in self._frames if frame == name)
        if votes < self.min_votes:
            return None
        action = ACTION_MAP[name]
        last = self._last_emitted.get(action)
        if last is not None and timestamp - last < self.cooldown_s:
            return None
        self._last_emitted[action] = timestamp
        confidence = min(1.0, 0.35 + 0.13 * votes)
        return GestureEvent(
            type=name,
            action=action,
            confidence=confidence,
            timestamp=timestamp,
        )

    def last_emitted(self) -> dict[str, float]:
        return dict(self._last_emitted)


def normalize_gesture(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if not value:
        return None
    value = value.replace("-", "_").replace(" ", "_")
    value = ALIASES.get(value, value)
    return value if value in ACTION_MAP else None


def vote_distribution(frames: list[str | None]) -> Counter[str]:
    return Counter(frame for frame in frames if frame is not None)
