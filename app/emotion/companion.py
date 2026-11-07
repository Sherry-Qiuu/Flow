"""T17 companion growth and reward economy."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from data.repositories import Repositories

logger = logging.getLogger(__name__)
LEVEL_THRESHOLDS = (0, 10, 30, 60, 100)
STAGES = ("幼芽", "小苗", "小树", "花期", "大树")
POINTS = {"step_done": 1, "task_done": 5, "on_time": 3, "streak_3": 10}


class CompanionService:
    def __init__(self, repos: Repositories, *, publisher: Any = None) -> None:
        self.repos = repos
        self.publisher = publisher

    def state(self) -> dict[str, Any]:
        row = self.repos.companion.get()
        raw = {}
        if row.get("state_json"):
            import json

            try:
                raw = json.loads(row["state_json"])
            except Exception:
                raw = {}
        exp = int(raw.get("exp", 0))
        level = self.level_for(exp)
        return {
            "exp": exp,
            "level": level,
            "stage": STAGES[level],
            "next_exp": (
                LEVEL_THRESHOLDS[level + 1]
                if level + 1 < len(LEVEL_THRESHOLDS)
                else None
            ),
            "streak": int(raw.get("streak", 0)),
            "daily_steps": int(raw.get("daily_steps", 0)),
            "last_active": raw.get("last_active", ""),
        }

    def award(self, kind: str, *, points: int | None = None) -> dict[str, Any]:
        state = self.state()
        amount = points if points is not None else POINTS.get(kind, 0)
        if amount <= 0:
            return state
        today = date.today().isoformat()
        yesterday = _yesterday(today)
        last = state["last_active"]
        streak = state["streak"]
        if last == today:
            pass
        elif last == yesterday:
            streak += 1
        else:
            streak = 1
        daily_steps = (
            state["daily_steps"] + (1 if kind == "step_done" else 0)
            if last == today
            else (1 if kind == "step_done" else 0)
        )
        exp = state["exp"] + amount
        payload = {
            "exp": exp,
            "level": self.level_for(exp),
            "streak": streak,
            "daily_steps": daily_steps,
            "last_active": today,
        }
        self.repos.companion.set(payload)
        self.repos.rewards.add(kind, points=amount, payload=payload)
        self._publish(
            "companion.changed",
            {
                **payload,
                "stage": STAGES[self.level_for(exp)],
                "kind": kind,
                "points": amount,
                "next_exp": _next_exp(exp),
            },
        )
        return self.state()

    def level_for(self, exp: int) -> int:
        level = 0
        for index, threshold in enumerate(LEVEL_THRESHOLDS):
            if exp >= threshold:
                level = index
        return min(level, len(STAGES) - 1)

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("companion publish failed")


def _next_exp(exp: int) -> int | None:
    for threshold in LEVEL_THRESHOLDS:
        if exp < threshold:
            return threshold
    return None


def _yesterday(today: str) -> str:
    from datetime import date as _date, timedelta

    return (_date.fromisoformat(today) - timedelta(days=1)).isoformat()
