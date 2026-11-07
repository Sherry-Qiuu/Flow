"""WebSocket transport: initial state.sync, fan-out and error handling."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from bus.event_bus import EventBus
from service import protocol
from service.logging import (
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)
from service.status import ServiceStatus

logger = logging.getLogger(__name__)

SnapshotProvider = Callable[[], dict[str, Any]]
MessageHandler = Callable[
    ["Connection", protocol.ClientMessage],
    Awaitable[None] | None,
]


@dataclass
class Connection:
    id: str
    websocket: WebSocket
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=200)
    )
    sender: asyncio.Task | None = None
    connected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def enqueue(self, message: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(message)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                logger.warning("websocket queue full; dropping event")


class WebSocketHub:
    def __init__(self, bus: EventBus, snapshot: SnapshotProvider) -> None:
        self.bus = bus
        self.snapshot = snapshot
        self._connections: dict[str, Connection] = {}
        self._handlers: dict[str, MessageHandler] = {}
        self._unsubscribe: Callable[[], None] | None = None
        self._started = False

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def start(self) -> ServiceStatus:
        if not self._started:
            self._unsubscribe = self.bus.subscribe(
                "*",
                self._broadcast,
                envelope=True,
            )
            self._started = True
        return ServiceStatus.ok(
            "websocket",
            f"{self.connection_count} active connection(s)",
        )

    def health(self) -> ServiceStatus:
        if not self._started:
            return ServiceStatus.error("websocket", "hub is not started")
        return ServiceStatus.ok(
            "websocket",
            f"{self.connection_count} active connection(s)",
        )

    async def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._started = False
        connections = list(self._connections.values())
        self._connections.clear()
        for connection in connections:
            if connection.sender is not None:
                connection.sender.cancel()
        for connection in connections:
            try:
                await connection.websocket.close(code=1001)
            except Exception:  # pragma: no cover - socket boundary
                pass
        senders = [
            connection.sender
            for connection in connections
            if connection.sender is not None
        ]
        if senders:
            await asyncio.gather(*senders, return_exceptions=True)

    def register_handler(
        self,
        message_type: str,
        handler: MessageHandler,
    ) -> Callable[[], None]:
        self._handlers[message_type] = handler

        def unregister() -> None:
            self._handlers.pop(message_type, None)

        return unregister

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        connection = Connection(
            id=uuid.uuid4().hex[:8],
            websocket=websocket,
        )
        self._connections[connection.id] = connection
        connection.sender = asyncio.create_task(
            self._send_loop(connection),
            name=f"ws-send-{connection.id}",
        )
        trace_token = set_trace_id(new_trace_id())
        logger.info(
            "ws.connected",
            extra={
                "event": "ws.connected",
                "client_id": connection.id,
            },
        )
        try:
            initial = self.bus.make_message(
                protocol.STATE_SYNC,
                self.snapshot(),
            )
            connection.enqueue(initial.to_dict())
            while True:
                raw = await websocket.receive_text()
                await self._handle_raw(connection, raw)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception(
                "websocket connection failed",
                extra={"client_id": connection.id},
            )
        finally:
            await self._disconnect(connection)
            reset_trace_id(trace_token)

    async def _disconnect(self, connection: Connection) -> None:
        self._connections.pop(connection.id, None)
        if connection.sender is not None:
            connection.sender.cancel()
            await asyncio.gather(
                connection.sender,
                return_exceptions=True,
            )
        logger.info(
            "ws.disconnected",
            extra={
                "event": "ws.disconnected",
                "client_id": connection.id,
            },
        )

    async def _send_loop(self, connection: Connection) -> None:
        try:
            while True:
                message = await connection.queue.get()
                await connection.websocket.send_text(
                    json.dumps(message, ensure_ascii=False)
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug(
                "websocket send loop ended",
                extra={"client_id": connection.id},
                exc_info=True,
            )

    async def _broadcast(self, envelope: dict[str, Any]) -> None:
        for connection in tuple(self._connections.values()):
            connection.enqueue(envelope)

    async def _handle_raw(
        self,
        connection: Connection,
        raw: str,
    ) -> None:
        try:
            message = protocol.parse_client_message(raw)
        except json.JSONDecodeError:
            self._send_error(
                connection,
                protocol.ERROR_INVALID_JSON,
                "message must be valid JSON",
            )
            return
        except (ValidationError, ValueError) as exc:
            detail = str(exc).splitlines()[0][:300]
            self._send_error(
                connection,
                protocol.ERROR_INVALID_MESSAGE,
                f"invalid message: {detail}",
            )
            return

        logger.info(
            "ws.message",
            extra={
                "event": "ws.message",
                "client_id": connection.id,
                "message_type": message.type,
            },
        )
        if message.type not in protocol.CLIENT_MESSAGE_TYPES:
            self._send_error(
                connection,
                protocol.ERROR_UNKNOWN_TYPE,
                f"unknown message type: {message.type}",
            )
            return
        handler = self._handlers.get(message.type)
        if handler is None:
            return
        try:
            result = handler(connection, message)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.exception(
                "client message handler failed",
                extra={"message_type": message.type},
            )
            self._send_error(
                connection,
                protocol.ERROR_INTERNAL,
                f"handler failed: {exc}",
            )

    def _send_error(
        self,
        connection: Connection,
        code: str,
        message: str,
    ) -> None:
        envelope = self.bus.make_message(
            protocol.ERROR,
            {"code": code, "message": message},
        )
        connection.enqueue(envelope.to_dict())
