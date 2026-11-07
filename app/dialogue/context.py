"""T08 dialogue context, slots and timeout policy."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from planner.timeutil import default_tz


@dataclass
class Turn:
    role: str
    text: str
    at: float
    source: str = "voice"


@dataclass
class DialogueContext:
    max_turns: int = 8
    timeout_s: float = 30.0
    turns: deque[Turn] = field(default_factory=lambda: deque(maxlen=8))
    channel: str = "idle"
    plan_draft: dict[str, Any] | None = None
    task_draft: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    last_active: float = 0.0

    def add(self, role: str, text: str, source: str = "voice") -> None:
        self.turns.append(Turn(role, text, time.monotonic(), source))
        self.last_active = time.monotonic()

    def timed_out(self, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        return bool(self.turns) and moment - self.last_active > self.timeout_s

    def expire_if_needed(self, now: float | None = None) -> bool:
        if self.timed_out(now):
            self.pending = None
            self.slots.clear()
            self.add("system", "idle_timeout")
            return True
        return False

    def summary(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "task_draft": self.task_draft,
            "plan_draft": self.plan_draft,
            "pending": self.pending,
            "slots": dict(self.slots),
            "turns": [
                {"role": turn.role, "text": turn.text}
                for turn in self.turns
            ],
        }
