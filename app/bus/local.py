"""A minimal in-process event bus.

It is intentionally small: synchronous handlers, thread-safe
subscription, and a failure in one handler never stops delivery to the
others. T03 can replace it with the WebSocket-aware bus while keeping
the ``EventPublisher`` protocol used by the HAL.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]


class LocalEventBus:
    """Thread-safe publish/subscribe bus for local components."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        """Register ``handler`` and return an unsubscribe callable."""
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            self._handlers[topic].append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(topic, [])
                if handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Deliver a copy of ``payload`` to every current subscriber."""
        with self._lock:
            handlers = tuple(self._handlers.get(topic, ()))
        for handler in handlers:
            try:
                handler(dict(payload))
            except Exception:  # pragma: no cover - defensive boundary
                logger.exception("event handler failed for %s", topic)

    def close(self) -> None:
        """Drop all subscriptions."""
        with self._lock:
            self._handlers.clear()
