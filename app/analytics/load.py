"""T19 load score and rest interventions."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from analytics.distraction import DistractionService
from bus import topics
from data.repositories import Repositories
from planner.timeutil import default_tz

logger = logging.getLogger(__name__)
REST_CATALOG = (
    {"id": "stretch", "title": "站起来伸个懒腰", "minutes": 3},
    {"id": "walk", "title": "走动一下，喝口水", "minutes": 5},
    {"id": "water", "title": "喝一杯水", "minutes": 2},
    {"id": "distance", "title": "看看远处，放松眼睛", "minutes": 3},
    {"id": "outside", "title": "到外面走一小圈", "minutes": 10},
)


class LoadService:
    def __init__(
        self,
        repos: Repositories,
        *,
        distractions: DistractionService | None = None,
        publisher: Any = None,
        say: Any = None,
        now_fn=None,
    ) -> None:
        self.repos = repos
        self.distractions = distractions
        self.publisher = publisher
        self.say = say
        self.now_fn = now_fn or (lambda: datetime.now(default_tz()))
        self._suppressed_until: datetime | None = None
        self._last_level = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="flow-load",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def score(self) -> dict[str, Any]:
        now = self.now_fn()
        today = now.astimezone(default_tz()).date()
        sessions = self.repos.focus_sessions.list(limit=100)
        focus_minutes = 0
        for row in sessions:
            started = _parse(row.get("started_at"))
            if started.astimezone(default_tz()).date() != today:
                continue
            ended = _parse(row.get("ended_at")) or now
            focus_minutes += max(
                0,
                int((ended - started).total_seconds() // 60),
            )
        distraction_count = (
            int(self.distractions.insights(1)["count"])
            if self.distractions is not None
            else 0
        )
        score = min(
            100,
            int(focus_minutes / 90 * 40)
            + distraction_count * 4
            + (15 if now.astimezone(default_tz()).hour >= 23 else 0),
        )
        if score >= 70:
            level = 2
        elif score >= 40:
            level = 1
        else:
            level = 0
        return {
            "score": score,
            "level": level,
            "focus_minutes": focus_minutes,
            "distractions": distraction_count,
            "suppressed": (
                self._suppressed_until is not None
                and now < self._suppressed_until
            ),
            "rest": REST_CATALOG[level % len(REST_CATALOG)],
            "rest_catalog": list(REST_CATALOG),
        }

    def acknowledge(self, hours: float = 2.0) -> None:
        self._suppressed_until = self.now_fn() + timedelta(hours=hours)

    def offer(self) -> dict[str, Any]:
        state = self.score()
        if state["level"] == 0 or state["suppressed"]:
            return {"offered": False, **state}
        self._publish(topics.REMINDER_FIRED, {
            "id": "load-rest",
            "title": state["rest"]["title"],
            "kind": "rest",
        })
        self._publish("rest.offered", state)
        if self.say is not None:
            self.say.say(
                state["rest"]["title"],
                emotion="concerned",
                priority="dialogue",
            )
        return {"offered": True, **state}

    def snapshot(self) -> dict[str, Any]:
        return self.score()

    def _loop(self) -> None:
        while not self._stop.wait(30.0):
            try:
                state = self.score()
                if state["level"] >= 2 and not state["suppressed"]:
                    self.offer()
                self._last_level = state["level"]
            except Exception:
                logger.exception("load check failed")

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("load publish failed")


def _parse(value: str | None) -> datetime:
    if not value:
        return datetime.now(default_tz())
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=default_tz())
