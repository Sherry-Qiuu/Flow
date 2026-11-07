"""Service lifecycle: db -> hal -> scheduler -> websocket."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from bus.event_bus import EventBus
from channel.base import ChannelContext
from channel.builtin import build_registry
from channel.machine import ChannelMachine
from channel.service import GESTURE_ACTIONS, ChannelService
from data.backup import DailyBackup
from data.database import DEFAULT_USER_ID
from data.repositories import Repositories, repositories
from gesture.service import GestureService
from hal.factory import Hal
from phone.service import PhoneSessionService
from service import protocol
from service.config import Settings
from service.db import Database
from service.hal_service import HalService
from service.logging import configure_logging
from service.scheduler_service import SchedulerService
from service.status import ServiceStatus
from service.ws import Connection, WebSocketHub
from voice.asr import build_asr
from voice.pipeline import SpeechPipeline

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(
        self,
        settings: Settings,
        bus: EventBus | None = None,
        hal: Hal | None = None,
    ) -> None:
        self.settings = settings
        self.bus = bus or EventBus()
        self.db = Database(settings.data.db_path)
        self.backup = DailyBackup(
            settings.data.db_path,
            backup_dir=settings.data.backup_dir,
            keep=settings.data.backup_keep,
            hour=settings.data.backup_hour,
        )
        self.hal = HalService(settings.hal, self.bus, hal)
        self.scheduler = SchedulerService(settings.scheduler)
        self.gesture: GestureService | None = None
        self.phone_sessions: PhoneSessionService | None = None
        self.repos: Repositories | None = None
        self.channels: ChannelService | None = None
        self.voice: SpeechPipeline | None = None
        self.hub = WebSocketHub(self.bus, self.snapshot)
        self.started_at: datetime | None = None
        self._started_monotonic = 0.0
        self._subsystems: dict[str, ServiceStatus] = {}
        self._stopping = False

    async def start(self) -> None:
        configure_logging(
            self.settings.logging.level,
            json_mode=self.settings.logging.json,
        )
        self.bus.bind_loop()
        self.started_at = datetime.now(timezone.utc)
        self._started_monotonic = time.monotonic()
        logger.info(
            "service.starting",
            extra={"event": "service.starting"},
        )
        await self._start("db", self.db.start, thread=True)
        self.backup.start()
        self.repos = repositories(
            self.db.connection,
            DEFAULT_USER_ID,
        )
        await self._start("hal", self.hal.start, thread=True)
        hal = self.hal.hal
        self.gesture = GestureService(
            self.settings.gesture,
            self.bus,
            gesture=hal.gesture if hal is not None else None,
            phone_stand=hal.phone_stand if hal is not None else None,
            subscriber=self.bus,
        )
        await self._start("gesture", self.gesture.start)
        self.phone_sessions = PhoneSessionService(
            hal.phone_stand if hal is not None else None,
            self.repos.phone_sessions,
            publisher=self.bus,
        )
        await self._start("phone", self.phone_sessions.start)
        self.machine = ChannelMachine(
            build_registry(),
            ChannelContext(
                user_id=DEFAULT_USER_ID,
                repos=self.repos,
            ),
            publisher=self.bus,
        )
        self.channels = ChannelService(
            self.machine,
            publisher=self.bus,
            subscriber=self.bus,
        )
        await self._start("channel", self.channels.start)
        self.voice = SpeechPipeline(
            hal.audio_in if hal is not None else None,
            build_asr(self.settings.voice),
            publisher=self.bus,
            audio_out=hal.audio_out if hal is not None else None,
            settings=self.settings.voice,
        )
        await self._start("voice", self.voice.start)
        await self._start("scheduler", self.scheduler.start)
        await self._start("websocket", self.hub.start)
        self._register_client_handlers()
        logger.info(
            "service.ready",
            extra={"event": "service.ready"},
        )

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        logger.info(
            "service.stopping",
            extra={"event": "service.stopping"},
        )
        await self.hub.stop()
        self.scheduler.stop()
        if self.voice is not None:
            self.voice.stop()
        if self.channels is not None:
            self.channels.stop()
        if self.phone_sessions is not None:
            self.phone_sessions.stop()
        if self.gesture is not None:
            self.gesture.stop()
        self.backup.stop()
        await asyncio.to_thread(self.hal.stop)
        await asyncio.to_thread(self.db.stop)
        await self.bus.aclose()
        logger.info(
            "service.stopped",
            extra={"event": "service.stopped"},
        )

    async def _start(
        self,
        name: str,
        start: Callable[[], Any],
        *,
        thread: bool = False,
    ) -> None:
        try:
            if thread:
                result = await asyncio.to_thread(start)
            else:
                result = start()
                if inspect.isawaitable(result):
                    result = await result
            status = result
            if not isinstance(status, ServiceStatus):
                status = ServiceStatus(
                    name,
                    getattr(result, "state", "ok"),
                    getattr(result, "detail", ""),
                )
        except Exception as exc:
            logger.exception(
                "subsystem failed to start",
                extra={"event": "subsystem.error", "device": name},
            )
            status = ServiceStatus.error(name, str(exc))
        self._subsystems[name] = status
        if not status.healthy:
            logger.warning(
                "subsystem degraded",
                extra={
                    "event": "subsystem.degraded",
                    "device": name,
                    "topic": status.state,
                },
            )

    def _register_client_handlers(self) -> None:
        """Give the three declared client message types a real receiver.

        Without this every websocket message was accepted and dropped, which
        is indistinguishable from a frozen screen.
        """
        self.hub.register_handler(
            protocol.USER_INTENT,
            self._on_user_intent,
        )
        self.hub.register_handler(
            protocol.UI_ACTION,
            self._on_ui_action,
        )
        self.hub.register_handler(
            protocol.FOCUS_CONTROL,
            self._on_focus_control,
        )

    def _on_user_intent(
        self,
        connection: Connection,
        message: protocol.ClientMessage,
    ) -> None:
        text = str(message.payload.get("text") or "").strip()
        if not self._channels_ready(connection):
            return
        if not text:
            self.hub.send_error(
                connection,
                protocol.ERROR_INVALID_MESSAGE,
                "intent text must not be empty",
            )
            return
        assert self.channels is not None
        self.channels.handle_text(text, source="ws")

    def _on_ui_action(
        self,
        connection: Connection,
        message: protocol.ClientMessage,
    ) -> None:
        action = str(message.payload.get("action") or "").strip().lower()
        if not self._channels_ready(connection):
            return
        if action not in GESTURE_ACTIONS:
            self.hub.send_error(
                connection,
                protocol.ERROR_INVALID_ACTION,
                f"unknown action: {action or '(missing)'}",
            )
            return
        assert self.channels is not None
        self.channels.handle_gesture({"action": action})

    def _on_focus_control(
        self,
        connection: Connection,
        message: protocol.ClientMessage,
    ) -> None:
        action = str(message.payload.get("action") or "").strip().lower()
        if not self._channels_ready(connection):
            return
        assert self.channels is not None
        if not self.channels.handle_command(action, source="ui"):
            self.hub.send_error(
                connection,
                protocol.ERROR_INVALID_ACTION,
                f"unknown focus command: {action or '(missing)'}",
            )

    def _channels_ready(self, connection: Connection) -> bool:
        if self.channels is not None:
            return True
        self.hub.send_error(
            connection,
            protocol.ERROR_NOT_READY,
            "channel service is not running",
        )
        return False

    def health_payload(self) -> dict[str, Any]:
        statuses = self._health_statuses()
        overall = (
            "ok"
            if all(status.healthy for status in statuses.values())
            else "degraded"
        )
        return {
            "status": overall,
            "version": self.settings.app.version,
            "started_at": self._started_at_iso(),
            "uptime_s": self._uptime(),
            "subsystems": {
                name: status.to_dict()
                for name, status in statuses.items()
            },
            "hal_faults": self.hal.faults(),
            "config": {
                "timezone": self.settings.app.timezone,
                "hal_backend": self.settings.hal.backend,
                "ui_size": self.settings.ui.size,
            },
        }

    def snapshot(self) -> dict[str, Any]:
        statuses = self._health_statuses()
        current = self._channel_state()
        phase = _phase_for(current)
        return {
            "version": self.settings.app.version,
            "started_at": self._started_at_iso(),
            "server_time": _utc_now_iso(),
            "uptime_s": self._uptime(),
            "phase": phase,
            "channel": _channel_key(current),
            "channel_state": current,
            "message": _message_for(current),
            "tasks_count": self._open_task_count(),
            "subsystems": {
                name: status.to_dict()
                for name, status in statuses.items()
            },
            "hal": self.hal.device_snapshot(),
            "phone": (
                self.phone_sessions.phone_state()
                if self.phone_sessions is not None
                else self.hal.phone_state()
            ),
            "phone_sessions": (
                self.phone_sessions.snapshot()
                if self.phone_sessions is not None
                else None
            ),
            "voice": (
                self.voice.snapshot()
                if self.voice is not None
                else None
            ),
            "gesture": (
                self.gesture.snapshot()
                if self.gesture is not None
                else {"enabled": False, "started": False}
            ),
            "ui": {"size": self.settings.ui.size},
        }

    def _channel_state(self) -> dict[str, Any] | None:
        if self.channels is None:
            return None
        return self.channels.snapshot()["current"]

    def _open_task_count(self) -> int:
        if self.repos is None:
            return 0
        try:
            return len(
                [task for task in self.repos.tasks.list() if not task.completed]
            )
        except Exception:  # pragma: no cover - database boundary
            logger.exception("failed to count tasks for the snapshot")
            return 0

    def _health_statuses(self) -> dict[str, ServiceStatus]:
        gesture_status = (
            self.gesture.health()
            if self.gesture is not None
            else None
        )
        phone_status = (
            self.phone_sessions.health()
            if self.phone_sessions is not None
            else None
        )
        voice_status = (
            self.voice.health()
            if self.voice is not None
            else None
        )
        return {
            "db": self.db.health(),
            "hal": self.hal.health(),
            "scheduler": self.scheduler.health(),
            "channel": (
                ServiceStatus(
                    "channel",
                    self.channels.health().state,
                    self.channels.health().detail,
                )
                if self.channels is not None
                else ServiceStatus.disabled(
                    "channel",
                    "channel service not started",
                )
            ),
            "gesture": (
                ServiceStatus(
                    "gesture",
                    gesture_status.state,
                    gesture_status.detail,
                )
                if gesture_status is not None
                else ServiceStatus.disabled(
                    "gesture",
                    "gesture service not started",
                )
            ),
            "phone": (
                ServiceStatus(
                    "phone",
                    phone_status.state,
                    phone_status.detail,
                )
                if phone_status is not None
                else ServiceStatus.disabled(
                    "phone",
                    "phone service not started",
                )
            ),
            "voice": (
                ServiceStatus(
                    "voice",
                    voice_status.state,
                    voice_status.detail,
                )
                if voice_status is not None
                else ServiceStatus.disabled(
                    "voice",
                    "voice service not started",
                )
            ),
            "websocket": self.hub.health(),
        }

    def _started_at_iso(self) -> str | None:
        if self.started_at is None:
            return None
        return self.started_at.isoformat()

    def _uptime(self) -> float:
        if self._started_monotonic <= 0:
            return 0.0
        return round(time.monotonic() - self._started_monotonic, 3)


def _channel_key(current: dict[str, Any] | None) -> str:
    if not current:
        return "clock"
    key = current.get("channel")
    return str(key) if key else "clock"


def _phase_for(current: dict[str, Any] | None) -> str:
    """Derive the screen phase from what is actually running.

    ``RuntimeState.phase`` was never written by anything, so a reconnecting
    client was told "idle" while a focus timer was ticking.
    """
    if not current:
        return "idle"
    if current.get("channel") == "focus":
        data = current.get("data")
        if isinstance(data, dict) and data.get("running"):
            return "executing"
    return "idle"


def _message_for(current: dict[str, Any] | None) -> str:
    hints = (current or {}).get("hints")
    if isinstance(hints, list) and hints:
        return str(hints[0])
    return ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
