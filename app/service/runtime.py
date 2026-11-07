"""Service lifecycle: db -> hal -> scheduler -> websocket."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from bus import topics
from bus.event_bus import EventBus
from analytics.collector import AnalyticsService
from analytics.distraction import DistractionService
from analytics.load import LoadService
from analytics.weekly import WeeklyReportService
from channel.base import ChannelContext
from channel.builtin import build_registry
from channel.machine import ChannelMachine
from channel.service import ChannelService
from capture.service import TaskCaptureService
from data.backup import DailyBackup
from data.database import DEFAULT_USER_ID
from data.repositories import Repositories, repositories
from degrade import DegradeMatrix
from demo.service import DemoService
from dialogue.policy import Dialogue
from emotion.celebrate import CelebrateService
from emotion.companion import CompanionService
from focus.service import FocusService
from hal.factory import Hal
from phone.contract import PhoneContractService
from phone.inbox import FileInbox
from phone.service import PhoneSessionService
from phone.usage import UsageService
from plan.service import PlanService
from planner.llm import default_engine
from planner.timeutil import tz_for
from recovery import RecoveryReport
from users.service import UserService
from service.config import Settings
from service.db import Database
from service.hal_service import HalService
from service.logging import configure_logging
from service.scheduler_service import SchedulerService
from service.status import ServiceStatus
from service.ws import Connection, WebSocketHub
from service import protocol
from voice.asr import build_asr
from voice.pipeline import SpeechPipeline
from voice.say import SayService, SaySettings
from voice.tts import EspeakTts

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
        self.phone_sessions: PhoneSessionService | None = None
        self.repos: Repositories | None = None
        self.channels: ChannelService | None = None
        self.voice: SpeechPipeline | None = None
        self.say_service: SayService | None = None
        self.phone_contract: PhoneContractService | None = None
        self.capture: TaskCaptureService | None = None
        self.plan_service: PlanService | None = None
        self.focus: FocusService | None = None
        self.companion: CompanionService | None = None
        self.celebrate: CelebrateService | None = None
        self.dialogue = Dialogue()
        self.users: UserService | None = None
        self.analytics: AnalyticsService | None = None
        self.distractions: DistractionService | None = None
        self.load: LoadService | None = None
        self.weekly: WeeklyReportService | None = None
        self.inbox: FileInbox | None = None
        self.usage: UsageService | None = None
        self.degrade = DegradeMatrix(self.hal)
        self.recovery = RecoveryReport(settings.data.dir)
        self.hub = WebSocketHub(self.bus, self.snapshot)
        self._tz = tz_for(settings.app.timezone)
        self._plan_unsubscribe: Callable[[], None] | None = None
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
        self.users = UserService(
            self.db.connection,
            active_user_id=DEFAULT_USER_ID,
        )
        await self._start("hal", self.hal.start, thread=True)
        hal = self.hal.hal
        self.say_service = SayService(
            tts=EspeakTts(),
            audio_out=hal.audio_out if hal is not None else None,
            publisher=self.bus,
            settings=SaySettings(
                cache_dir=str(self.settings.data.dir / "audio" / "cache")
            ),
        )
        self.say_service.start()
        self.phone_sessions = PhoneSessionService(
            hal.phone_stand if hal is not None else None,
            self.repos.phone_sessions,
            publisher=self.bus,
        )
        await self._start("phone", self.phone_sessions.start)
        self.capture = TaskCaptureService(
            self.repos,
            publisher=self.bus,
            camera=hal.camera if hal is not None else None,
            inbox=str(self.settings.data.dir / "inbox"),
        )
        self.plan_service = PlanService(
            self.repos,
            publisher=self.bus,
            engine=default_engine(
                settings=self.settings.llm,
                cache_path=self.settings.data.dir / "llm_cache.json",
            ),
        )
        self.analytics = AnalyticsService(
            self.repos,
            publisher=self.bus,
        )
        self.distractions = DistractionService(
            self.repos,
            publisher=self.bus,
        )
        self.weekly = WeeklyReportService(
            self.repos,
            self.analytics,
            distractions=self.distractions,
            export_dir=self.settings.data.dir / "exports",
        )
        self.load = LoadService(
            self.repos,
            distractions=self.distractions,
            publisher=self.bus,
            say=self.say_service,
        )
        self.inbox = FileInbox(
            self.settings.data.dir / "inbox",
            publisher=self.bus,
        )
        self.usage = UsageService(
            self.settings.data.dir / "phone_usage.json",
        )
        self.companion = CompanionService(
            self.repos,
            publisher=self.bus,
        )
        self.celebrate = CelebrateService(
            self.companion,
            publisher=self.bus,
            say=self.say_service,
            subscriber=self.bus,
        )
        self.focus = FocusService(
            self.repos,
            publisher=self.bus,
            say=self.say_service,
            store_path=self.settings.data.dir / "focus_state.json",
            now_fn=lambda: datetime.now(self._tz),
        )
        self.phone_contract = PhoneContractService(
            self.repos.phone_sessions,
            publisher=self.bus,
            say=self.say_service,
            subscriber=self.bus,
        )
        await self._start("contract", self.phone_contract.start)
        self.machine = ChannelMachine(
            build_registry(),
            ChannelContext(
                user_id=DEFAULT_USER_ID,
                repos=self.repos,
                now=lambda: datetime.now(self._tz),
                focus=self.focus,
            ),
            publisher=self.bus,
        )
        self.channels = ChannelService(
            self.machine,
            publisher=self.bus,
            subscriber=self.bus,
        )
        await self._start("channel", self.channels.start)
        self._plan_unsubscribe = self.bus.subscribe(
            topics.PLAN_REQUESTED,
            self._on_plan_requested,
        )
        await self._start("celebrate", self.celebrate.start)
        await self._start("focus", self.focus.start)
        self.load.start()
        self.voice = SpeechPipeline(
            hal.audio_in if hal is not None else None,
            build_asr(self.settings.voice),
            publisher=self.bus,
            audio_out=hal.audio_out if hal is not None else None,
            settings=self.settings.voice,
        )
        await self._start("voice", self.voice.start)
        self.scheduler.repo = self.repos.reminders
        self.scheduler.publisher = self.bus
        self.scheduler.say = self.say_service
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
        if self._plan_unsubscribe is not None:
            self._plan_unsubscribe()
            self._plan_unsubscribe = None
        self.scheduler.stop()
        if self.voice is not None:
            self.voice.stop()
        if self.channels is not None:
            self.channels.stop()
        if self.load is not None:
            self.load.stop()
        if self.focus is not None:
            self.focus.stop()
        if self.celebrate is not None:
            self.celebrate.stop()
        if self.phone_contract is not None:
            self.phone_contract.stop()
        if self.phone_sessions is not None:
            self.phone_sessions.stop()
        if self.say_service is not None:
            self.say_service.stop()
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

    def _on_plan_requested(self, payload: dict[str, Any]) -> None:
        """Turn what the user said into tasks, then into a plan.

        The words are the task list: 「写论文，背50个单词」 arrives here as the
        plan request text. Extract, commit, plan from the repo. Repeating the
        same sentence adds nothing — capture dedupes against stored titles.
        """
        if self.plan_service is None or self.repos is None:
            return
        text = str(payload.get("text") or "").strip()
        try:
            if text and self.capture is not None:
                drafts = self.capture.from_text(text, source="voice")
                if drafts:
                    self.capture.commit(drafts)
            if not self._open_task_count():
                # An empty review page is worse than asking again.
                self.bus.publish(
                    topics.ASSISTANT_SAY,
                    {"text": "先告诉我今天要做什么，比如「写论文，背50个单词」"},
                )
                return
            self.plan_service.create_from_repo()
        except Exception:
            logger.exception("plan request failed")

    def _register_client_handlers(self) -> None:
        """Give the three declared client message types a real receiver."""
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
        assert self.channels is not None
        if not self.channels.handle_command(action, source="touch"):
            self.hub.send_error(
                connection,
                protocol.ERROR_INVALID_ACTION,
                f"unknown action: {action or '(missing)'}",
            )

    def _on_focus_control(
        self,
        connection: Connection,
        message: protocol.ClientMessage,
    ) -> None:
        action = str(message.payload.get("action") or "").strip().lower()
        if not self._channels_ready(connection):
            return
        assert self.channels is not None
        if not self.channels.handle_command(action, source="touch"):
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
                # T12: whether the LLM path is on; the key itself never leaks.
                "llm_enabled": self.settings.llm.available,
                "llm_model": self.settings.llm.model,
            },
        }

    def switch_user(self, user_id: str) -> dict[str, Any]:
        if self.users is None:
            raise RuntimeError("users are not ready")
        user = self.users.switch(user_id)
        repos = self.users.repos(user_id)
        self.repos = repos
        if self.capture is not None:
            self.capture.repos = repos
        if self.plan_service is not None:
            self.plan_service.repos = repos
        if self.companion is not None:
            self.companion.repos = repos
        if self.analytics is not None:
            self.analytics.repos = repos
        if self.distractions is not None:
            self.distractions.repos = repos
        if self.weekly is not None:
            self.weekly.repos = repos
        if self.load is not None:
            self.load.repos = repos
        if self.focus is not None:
            self.focus.switch_user(
                repos,
                self.settings.data.dir / f"focus_state_{user_id}.json",
            )
        if self.phone_sessions is not None:
            self.phone_sessions.switch_repo(repos.phone_sessions)
        if self.phone_contract is not None:
            if self.phone_contract.active is not None:
                self.phone_contract.end("user_switch")
            self.phone_contract.repo = repos.phone_sessions
        if self.channels is not None:
            self.channels.machine.ctx.repos = repos
            self.channels.machine.ctx.user_id = user_id
        if self.scheduler.settings.enabled:
            self.scheduler.stop()
            self.scheduler.repo = repos.reminders
            self.scheduler.publisher = self.bus
            self.scheduler.say = self.say_service
            self.scheduler.start()
        return {"user": user, "active": user_id}

    def snapshot(self) -> dict[str, Any]:
        statuses = self._health_statuses()
        channel_state = (
            self.channels.snapshot()["current"]
            if self.channels is not None
            else None
        )
        if (
            self.phone_contract is not None
            and self.phone_contract.active is not None
        ):
            channel_state = self.phone_contract.active.snapshot(
                self.phone_contract.now_fn()
            )
        focus_state = (
            self.focus.snapshot() if self.focus is not None else None
        )
        focus_plan = self._plan_for_focus()
        draft_plan = self._open_draft_plan()
        phase = _phase_for(channel_state, focus_state, draft_plan is not None)
        return {
            "version": self.settings.app.version,
            "started_at": self._started_at_iso(),
            "server_time": _utc_now_iso(),
            "uptime_s": self._uptime(),
            "phase": phase,
            "channel": _channel_key(channel_state),
            "channel_state": channel_state,
            "message": _message_for(channel_state, phase),
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
            "say": (
                self.say_service.health()
                if self.say_service is not None
                else None
            ),
            "phone_contract": (
                self.phone_contract.snapshot()
                if self.phone_contract is not None
                else None
            ),
            "scheduler": self.scheduler.snapshot(),
            "companion": (
                self.companion.state()
                if self.companion is not None
                else None
            ),
            "active_user": (
                self.users.active_user_id
                if self.users is not None
                else DEFAULT_USER_ID
            ),
            "degrade": self.degrade.snapshot(),
            "recovery": self.recovery.snapshot(),
            "step": (
                focus_state
                if focus_state is not None
                and focus_state.get("status") != "idle"
                else None
            ),
            "focus": focus_state,
            "plan": focus_plan or draft_plan,
            "capture": {
                "camera": bool(
                    self.hal.hal is not None
                    and self.hal.hal.camera is not None
                ),
            },
            "ui": {"size": self.settings.ui.size},
        }

    def _channel_state(self) -> dict[str, Any] | None:
        if self.channels is None:
            return None
        return self.channels.snapshot()["current"]

    def _plan_for_focus(self) -> dict[str, Any] | None:
        if self.repos is None or self.focus is None:
            return None
        plan_id = self.focus.state.plan_id
        if not plan_id:
            return None
        plan = self.repos.plans.get(plan_id)
        return plan.to_dict() if plan is not None else None

    def _open_draft_plan(self) -> dict[str, Any] | None:
        """A draft still waiting for confirmation becomes the review page.

        Only today's draft counts: yesterday's abandoned plan must not hijack
        the screen every time the kiosk reconnects.
        """
        if self.repos is None:
            return None
        today = datetime.now(self._tz).date().isoformat()
        try:
            for row in self.repos.plans.list():
                if row["status"] != "draft":
                    continue
                if str(row["plan_date"]) != today:
                    continue
                plan = self.repos.plans.get(str(row["id"]))
                return plan.to_dict() if plan is not None else None
        except Exception:  # pragma: no cover - database boundary
            logger.exception("could not look up the draft plan")
        return None

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _channel_key(current: dict[str, Any] | None) -> str:
    if not current:
        return "clock"
    key = current.get("channel")
    return str(key) if key else "clock"


def _phase_for(
    current: dict[str, Any] | None,
    focus_state: dict[str, Any] | None = None,
    has_draft_plan: bool = False,
) -> str:
    """Derive the screen phase from what is actually running.

    The focus timer is owned by FocusService, not by the channel, so a
    running session has to win even when the channel stack is empty --
    otherwise a reconnect during a session shows the idle screen while the
    clock keeps counting down.
    """
    status = (focus_state or {}).get("status")
    if status in {"running", "paused"}:
        return "executing"
    if has_draft_plan:
        return "plan_review"
    if not current:
        return "idle"
    if current.get("channel") == "focus":
        data = current.get("data")
        if isinstance(data, dict) and data.get("running"):
            return "executing"
    return "idle"


def _message_for(
    current: dict[str, Any] | None,
    phase: str = "idle",
) -> str:
    if phase == "executing":
        return "只做眼前这一步。"
    if phase == "plan_review":
        return "这份计划可以吗？"
    hints = (current or {}).get("hints")
    if isinstance(hints, list) and hints:
        return str(hints[0])
    return ""
