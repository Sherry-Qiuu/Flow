"""T04 channel service: speech.final -> router -> machine -> 1 Hz tick."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from bus import topics
from channel.base import Action, ChannelContext, Intent
from channel.machine import ChannelMachine
from channel.registry import ChannelRegistry
from channel.router import route

logger = logging.getLogger(__name__)

# Gestures that the controller is allowed to turn into intents. ``ui.action``
# carries the same vocabulary over the websocket.
GESTURE_ACTIONS = frozenset(
    {
        "confirm",
        "next",
        "prev",
        "extend",
        "shorten",
        "finish_step",
        "skip_step",
        "channel_next",
        "channel_prev",
    }
)

# Action types that drive the machine itself rather than the screen.
_CONTROL_ACTIONS = frozenset({"back", "channel.snapshot"})

# ``focus.control`` from the touch UI; these are intent names, not gestures.
FOCUS_COMMANDS = frozenset({"start", "resume", "pause", "finish", "stop"})


def _gesture_mapping() -> dict[str, Intent]:
    return {
        "confirm": Intent("start", source="gesture"),
        "next": Intent("next", source="gesture"),
        "prev": Intent("back", source="gesture"),
        "extend": Intent("start", source="gesture"),
        "shorten": Intent("pause", source="gesture"),
        "finish_step": Intent("finish", source="gesture"),
        "skip_step": Intent("next", source="gesture"),
        "channel_next": Intent(
            "open_tool",
            tool="tasks",
            source="gesture",
        ),
        "channel_prev": Intent("back", source="gesture"),
    }


class ChannelHealth:
    def __init__(self, state: str, detail: str = "") -> None:
        self.state = state
        self.detail = detail

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


class ChannelService:
    def __init__(
        self,
        machine: ChannelMachine,
        *,
        publisher: Any = None,
        subscriber: Any = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.machine = machine
        self.publisher = publisher
        self.subscriber = subscriber
        self.clock = clock
        self._unsubscribe: Callable[[], None] | None = None
        self._unsubscribe_gesture: Callable[[], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_text = ""
        self._last_intent: Intent | None = None
        self._last_error = ""

    def start(self) -> ChannelHealth:
        if self.subscriber is not None:
            self._unsubscribe = self.subscriber.subscribe(
                topics.SPEECH_FINAL,
                self._on_speech,
            )
            self._unsubscribe_gesture = self.subscriber.subscribe(
                topics.GESTURE_DETECTED,
                self._on_gesture,
            )
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._tick_loop,
            name="flow-channel-tick",
            daemon=True,
        )
        self._thread.start()
        return ChannelHealth("ok", "channel machine running")

    def stop(self) -> None:
        self._stop.set()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._unsubscribe_gesture is not None:
            self._unsubscribe_gesture()
            self._unsubscribe_gesture = None
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def handle_text(self, text: str, *, source: str = "voice") -> list[Action]:
        intent = route(text, source=source)
        self._last_text = text
        self._last_intent = intent
        self._publish(topics.INTENT_PARSED, intent.to_dict())
        actions = self.machine.handle_intent(intent)
        self._publish_actions(actions)
        return actions

    def handle_gesture(self, payload: dict[str, Any]) -> list[Action]:
        action = str(payload.get("action", ""))
        intent = _gesture_mapping().get(action)
        if intent is None:
            return []
        actions = self.machine.handle_intent(intent)
        self._publish_actions(actions)
        return actions

    def handle_command(
        self,
        name: str,
        *,
        source: str = "client",
    ) -> list[Action]:
        """Run an intent by name, used by touch controls such as focus."""
        command = str(name).strip().lower()
        if command not in FOCUS_COMMANDS:
            return []
        actions = self.machine.handle_intent(
            Intent(command, source=source)
        )
        self._publish_actions(actions)
        return actions

    def snapshot(self) -> dict[str, Any]:
        return {
            "current": self.machine.snapshot(),
            "channels": self.machine.registry.list(),
            "stack": self.machine.stack_keys,
            "overloaded": self.machine.overloaded,
        }

    @property
    def last_intent(self) -> Intent | None:
        return self._last_intent

    @property
    def last_text(self) -> str:
        return self._last_text

    def health(self) -> ChannelHealth:
        if self._thread is None or not self._thread.is_alive():
            return ChannelHealth(
                "error",
                self._last_error or "channel tick is not running",
            )
        return ChannelHealth("ok", "channel machine running")

    def _on_speech(self, payload: dict[str, Any]) -> None:
        text = str(payload.get("text", "")).strip()
        if text:
            try:
                self.handle_text(text)
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("channel speech handling failed")

    def _on_gesture(self, payload: dict[str, Any]) -> None:
        try:
            self.handle_gesture(payload)
        except Exception:
            logger.exception("channel gesture handling failed")

    def _tick_loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                actions = self.machine.tick()
                self._publish_actions(actions)
            except Exception:
                logger.exception("channel tick failed")

    def _publish_actions(self, actions: list[Action]) -> None:
        for action in actions:
            if action.type == "speak":
                # The screen owns all copy; without this the robot reasons
                # correctly and never says anything.
                text = str(action.payload.get("text", "")).strip()
                if text:
                    self._publish(topics.ASSISTANT_SAY, {"text": text})
                continue
            if action.type in _CONTROL_ACTIONS:
                continue
            self._publish(action.type, action.payload)

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("channel publish failed: %s", topic)
