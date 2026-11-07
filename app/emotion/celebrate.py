"""T16 three-level celebration with quiet suppression."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any

from bus import topics
from emotion.companion import CompanionService, POINTS
from emotion.phrases import check_phrase, pick_phrase

logger = logging.getLogger(__name__)


class CelebrateService:
    def __init__(
        self,
        companion: CompanionService,
        *,
        publisher: Any = None,
        say: Any = None,
        subscriber: Any = None,
        night_start: int = 22,
        night_end: int = 7,
        merge_after: int = 5,
    ) -> None:
        self.companion = companion
        self.publisher = publisher
        self.say = say
        self.subscriber = subscriber
        self.night_start = night_start
        self.night_end = night_end
        self.merge_after = max(2, merge_after)
        self._recent: deque[str] = deque(maxlen=10)
        self._last_phrase = ""
        self._last_at = 0.0
        self._unsubscribe = None

    def start(self) -> "CelebrateHealth":
        if self.subscriber is not None:
            self._unsubscribe = self.subscriber.subscribe(
                topics.REWARD_EVENT,
                self._on_reward,
            )
        return CelebrateHealth("ok", "celebration running")

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def celebrate(
        self,
        kind: str = "step_done",
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        points = POINTS.get(kind, 0)
        state = self.companion.award(kind, points=points)
        self._recent.append(kind)
        merged = (
            len(self._recent) >= self.merge_after
            and all(item == "step_done" for item in self._recent)
        )
        phrase = pick_phrase(self._last_phrase)
        if merged:
            phrase = "这几步连在一起，已经走了一小段路。"
            self._recent.clear()
        if not check_phrase(phrase):
            phrase = "这一小步，稳稳的。"
        self._last_phrase = phrase
        night = _is_night(now or datetime.now(),
                          self.night_start, self.night_end)
        payload = {
            "kind": kind,
            "message": phrase,
            "emotion": "happy" if not night else "resting",
            "exp": state["exp"],
            "level": state["level"],
            "stage": state["stage"],
            "merged": merged,
            "night": night,
        }
        self._publish(topics.REWARD_FEEDBACK, payload)
        if self.say is not None:
            self.say.say(
                phrase,
                emotion=payload["emotion"],
                priority="chat",
            )
        self._last_at = time.monotonic()
        return payload

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.companion.state(),
            "recent": list(self._recent),
        }

    def _on_reward(self, payload: dict[str, Any]) -> None:
        try:
            self.celebrate(str(payload.get("kind", "step_done")))
        except Exception:
            logger.exception("celebration failed")

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("celebration publish failed")


class CelebrateHealth:
    def __init__(self, state: str, detail: str = "") -> None:
        self.state = state
        self.detail = detail

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _is_night(now: datetime, start: int, end: int) -> bool:
    hour = now.hour
    return hour >= start or hour < end
