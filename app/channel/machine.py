"""Single-channel state machine with return stack and overload guard."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from bus import topics
from channel import focus_verbs
from channel.base import Action, Channel, ChannelContext, Intent
from channel.registry import ChannelRegistry

logger = logging.getLogger(__name__)

# Verbs that act on the running timer rather than on the current channel.
_FOCUS_VERBS = frozenset({"skip", "extend", "status", "split", "stuck"})


class ChannelMachine:
    def __init__(
        self,
        registry: ChannelRegistry,
        ctx: ChannelContext,
        *,
        publisher: Any = None,
        max_stack: int = 3,
        switch_limit: int = 12,
        switch_window_s: float = 1800.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry
        self.ctx = ctx
        self.publisher = publisher
        self.max_stack = max(1, min(3, int(max_stack)))
        self.switch_limit = max(1, int(switch_limit))
        self.switch_window_s = max(1.0, float(switch_window_s))
        self.clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._current: Channel | None = None
        self._stack: deque[tuple[str, dict[str, Any]]] = deque(
            maxlen=self.max_stack
        )
        self._switches: deque[float] = deque()
        self._overloaded = False
        self._last_error = ""

    @property
    def current_key(self) -> str | None:
        return self._current.key if self._current is not None else None

    @property
    def overloaded(self) -> bool:
        with self._lock:
            self._prune_switches()
            return self._overloaded

    @property
    def stack_keys(self) -> list[str]:
        with self._lock:
            return [entry[0] for entry in self._stack]

    def activate(
        self,
        key: str,
        args: dict[str, Any] | None = None,
        *,
        push_stack: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            if self._current is not None and self._current.key == key:
                return self._current.snapshot()
            previous = (
                (self._current.key, {})
                if self._current is not None
                else None
            )
            if self._current is not None:
                self._exit_locked()
            try:
                channel = self.registry.get(key)
                snapshot = channel.enter(self.ctx, args or {})
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("channel enter failed: %s", key)
                self._publish(
                    topics.ERROR,
                    {"message": "刚才出了点问题，我们回到主页"},
                )
                return self.idle_snapshot()

            self._current = channel
            if push_stack and previous is not None:
                self._stack.append(previous)
            self._record_switch()
            payload = {
                "channel": channel.key,
                "title": channel.title,
                "snapshot": snapshot,
                "stack": [entry[0] for entry in self._stack],
            }
            self._publish(topics.CHANNEL_ENTER, payload)
            if self._overloaded:
                snapshot = self._with_hint(
                    snapshot,
                    "切换有点频繁，我们先专注在当前通道",
                )
            return snapshot

    def back(self) -> dict[str, Any]:
        with self._lock:
            if not self._stack:
                return self.deactivate()
            key, args = self._stack.pop()
            return self.activate(key, args, push_stack=False)

    def deactivate(self) -> dict[str, Any]:
        with self._lock:
            had_current = self._current is not None
            self._exit_locked()
            self._stack.clear()
            self._overloaded = False
            if not had_current:
                self._publish(
                    topics.CHANNEL_EXIT,
                    {"channel": None},
                )
            return self.idle_snapshot()

    def handle_intent(self, intent: Intent) -> list[Action]:
        with self._lock:
            if intent.name == "make_plan":
                return [Action(topics.PLAN_REQUESTED, {"text": intent.text})]
            if intent.name == "discourage":
                # 「太难了」 is a feeling. Inside a timer it means "this step is
                # too big" (FocusService shrinks it); anywhere else it gets a
                # reply, never a task named after the sentence.
                if (
                    self._current is not None
                    and self._current.key == "focus"
                ):
                    return self._current.handle(
                        Intent(
                            "stuck",
                            text=intent.text,
                            source=intent.source,
                        )
                    )
                return [
                    Action(
                        "speak",
                        {"text": focus_verbs.COMFORT_REPLY},
                    )
                ]
            if intent.name in _FOCUS_VERBS and (
                self._current is None or self._current.key != "focus"
            ):
                actions = focus_verbs.handle(
                    getattr(self.ctx, "focus", None),
                    intent,
                )
                if actions is not None:
                    return actions
            if intent.name == "return":
                if (
                    self._current is not None
                    and self._current.key == "focus"
                ):
                    return self._current.handle(
                        Intent("status", source=intent.source)
                    )
                return [
                    Action(
                        "speak",
                        {"text": "我在。要不要说“打开任务清单”接着来？"},
                    )
                ]
            if intent.name == "open_tool":
                if not intent.tool or not self.registry.has(intent.tool):
                    return [
                        Action(
                            "speak",
                            {"text": "这个工具还没准备好"},
                        )
                    ]
                snapshot = self.activate(intent.tool, intent.args)
                return [Action("channel.snapshot", snapshot)]
            if intent.name == "back":
                snapshot = self.back()
                return [Action("channel.snapshot", snapshot)]
            if intent.name == "clarify":
                return [
                    Action(
                        "speak",
                        {
                            "text": intent.args.get(
                                "reply",
                                "你是想专注计时还是看任务清单？",
                            )
                        },
                    )
                ]
            if intent.name == "unknown":
                return [
                    Action(
                        "speak",
                        {"text": "我还没听懂，可以说“打开任务清单”"},
                    )
                ]
            if (
                intent.name in {"start", "resume"}
                and intent.args.get("open_focus")
                and (self._current is None or self._current.key != "focus")
                and self.registry.has("focus")
            ):
                # "开始专注" from the home screen: open the channel and
                # start in one step instead of asking again.
                self.activate("focus", {"minutes": intent.args.get("minutes")})
            if self._current is None:
                return [
                    Action(
                        "speak",
                        {"text": "先说“打开任务清单”试试"},
                    )
                ]
            try:
                actions = self._current.handle(intent)
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("channel handler failed: %s",
                                 self._current.key)
                self.deactivate()
                self._publish(
                    topics.ERROR,
                    {"message": "刚才出了点问题，我们回到主页"},
                )
                return [
                    Action(
                        "speak",
                        {"text": "刚才出了点问题，我们回到主页"},
                    )
                ]
            return actions

    def tick(self, now=None) -> list[Action]:
        with self._lock:
            if self._current is None:
                return []
            moment = now or self.ctx.now()
            try:
                actions = self._current.tick(moment)
            except Exception:
                logger.exception("channel tick failed")
                self.deactivate()
                return []
            return actions

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._current is None:
                return self.idle_snapshot()
            return self._current.snapshot()

    def idle_snapshot(self) -> dict[str, Any]:
        return {
            "channel": "idle",
            "title": "主页",
            "data": {},
            "hints": ["说“打开任务清单”或“开始专注”"],
        }

    def _exit_locked(self) -> None:
        current = self._current
        if current is None:
            return
        try:
            current.exit()
        except Exception:
            logger.exception("channel exit failed: %s", current.key)
        self._current = None
        self._publish(topics.CHANNEL_EXIT, {"channel": current.key})

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("failed to publish %s", topic)

    def _record_switch(self) -> None:
        now = self.clock()
        self._switches.append(now)
        self._prune_switches()
        if len(self._switches) >= self.switch_limit:
            self._overloaded = True

    def _prune_switches(self) -> None:
        cutoff = self.clock() - self.switch_window_s
        while self._switches and self._switches[0] < cutoff:
            self._switches.popleft()
        if len(self._switches) < self.switch_limit:
            self._overloaded = False

    @staticmethod
    def _with_hint(
        snapshot: dict[str, Any],
        hint: str,
    ) -> dict[str, Any]:
        copy = dict(snapshot)
        copy["hints"] = list(snapshot.get("hints", [])) + [hint]
        return copy
