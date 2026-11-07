"""T04 channel contract and shared context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from data.repositories import Repositories
from planner.timeutil import default_tz


@dataclass(frozen=True)
class Intent:
    name: str
    text: str = ""
    source: str = "voice"
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "text": self.text,
            "source": self.source,
            "tool": self.tool,
            "args": dict(self.args),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Action:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "payload": dict(self.payload)}


@dataclass
class ChannelContext:
    user_id: str = "u_default"
    repos: Repositories | None = None
    now: Callable[[], datetime] = lambda: datetime.now(default_tz())
    publish: Callable[[str, dict[str, Any]], None] | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    # The focus channel delegates timing to FocusService so the kiosk gets
    # one ``focus.state`` stream instead of two competing ones.
    focus: Any = None


class Channel(ABC):
    key: str
    title: str

    def __init__(self) -> None:
        self.ctx: ChannelContext | None = None
        self._snapshot: dict[str, Any] = {
            "channel": self.key,
            "title": self.title,
            "data": {},
            "hints": [],
        }

    @abstractmethod
    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def exit(self) -> None:
        ...

    @abstractmethod
    def handle(self, intent: Intent) -> list[Action]:
        ...

    @abstractmethod
    def tick(self, now: datetime) -> list[Action]:
        ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        ...

    def _finish(
        self,
        data: dict[str, Any],
        hints: list[str] | None = None,
    ) -> dict[str, Any]:
        self._snapshot = {
            "channel": self.key,
            "title": self.title,
            "data": data,
            "hints": list(hints or []),
        }
        return self._snapshot


class BaseChannel(Channel):
    """Default snapshot bookkeeping for the six built-in channels."""

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del args
        self.ctx = ctx
        return self._finish({}, self._default_hints())

    def exit(self) -> None:
        self.ctx = None

    def handle(self, intent: Intent) -> list[Action]:
        del intent
        return []

    def tick(self, now: datetime) -> list[Action]:
        del now
        return []

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot

    def _default_hints(self) -> list[str]:
        return []

    def _repos(self) -> Repositories | None:
        return self.ctx.repos if self.ctx is not None else None
