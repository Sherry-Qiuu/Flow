"""Asyncio event bus with thread-safe publishing for HAL watchers."""

from __future__ import annotations

import asyncio
import fnmatch
import inspect
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass(frozen=True)
class EventMessage:
    """One enveloped event: ``{type, payload, seq, ts}``."""

    type: str
    payload: dict[str, Any]
    seq: int
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": dict(self.payload),
            "seq": self.seq,
            "ts": self.ts,
        }


@dataclass(frozen=True)
class _Subscription:
    token: int
    topic: str
    handler: Handler
    envelope: bool


class EventBus:
    """Thread-safe asyncio bus.

    ``publish`` can be called from hardware threads; it schedules
    delivery onto the application event loop. ``publish_async`` awaits
    delivery immediately for backend code already on that loop.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self._subscriptions: list[_Subscription] = []
        self._lock = threading.RLock()
        self._seq = 0
        self._token = 0
        self._closed = False
        self._tasks: set[asyncio.Task] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    def make_message(
        self,
        message_type: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        """Build an envelope without publishing it."""
        with self._lock:
            self._seq += 1
            seq = self._seq
        timestamp = datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        return EventMessage(
            type=message_type,
            payload=dict(payload or {}),
            seq=seq,
            ts=timestamp,
        )

    def subscribe(
        self,
        topic: str,
        handler: Handler,
        *,
        envelope: bool = False,
    ) -> Callable[[], None]:
        """Subscribe to an exact topic or an fnmatch pattern such as ``*``."""
        if not topic:
            raise ValueError("topic must not be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            self._token += 1
            subscription = _Subscription(
                self._token,
                topic,
                handler,
                envelope,
            )
            self._subscriptions.append(subscription)

        def unsubscribe() -> None:
            with self._lock:
                if subscription in self._subscriptions:
                    self._subscriptions.remove(subscription)

        return unsubscribe

    def publish(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        """Synchronous publish used by the HAL's EventPublisher protocol."""
        return self.publish_threadsafe(topic, payload)

    async def publish_async(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        """Publish and await all matching handlers."""
        message = self.make_message(topic, payload)
        await self._dispatch(message)
        return message

    def publish_threadsafe(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        """Publish from a worker thread; delivery is scheduled on the loop."""
        message = self.make_message(topic, payload)
        loop = self._loop
        if (
            self._closed
            or loop is None
            or loop.is_closed()
            or not loop.is_running()
        ):
            logger.debug("event dropped, loop unavailable: %s", topic)
            return message
        try:
            loop.call_soon_threadsafe(self._schedule, message)
        except RuntimeError:
            logger.debug("event dropped, loop closed: %s", topic)
        return message

    # Compatibility alias for callers that want the thread-safe name.
    def publish_nowait(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        return self.publish_threadsafe(topic, payload)

    # EventPublisher protocol used by the HAL.
    def publish_sync(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> EventMessage:
        return self.publish_threadsafe(topic, payload)

    def _schedule(self, message: EventMessage) -> None:
        if self._closed:
            return
        task = asyncio.create_task(self._dispatch(message))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _dispatch(self, message: EventMessage) -> None:
        with self._lock:
            subscriptions = tuple(self._subscriptions)
        for subscription in subscriptions:
            if not fnmatch.fnmatchcase(message.type, subscription.topic):
                continue
            value = (
                message.to_dict()
                if subscription.envelope
                else dict(message.payload)
            )
            try:
                result = subscription.handler(value)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # pragma: no cover - handler boundary
                logger.exception(
                    "event handler failed for %s on %s",
                    subscription.topic,
                    message.type,
                )

    async def aclose(self) -> None:
        self._closed = True
        with self._lock:
            subscriptions = tuple(self._subscriptions)
            self._subscriptions.clear()
        del subscriptions
        tasks = tuple(self._tasks)
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def close_nowait(self) -> None:
        """Close without awaiting; useful during interpreter shutdown."""
        self._closed = True
        with self._lock:
            self._subscriptions.clear()
