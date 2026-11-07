"""T04 channel machine, router, service and API tests."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from bus.local import LocalEventBus
from channel.base import Action, BaseChannel, ChannelContext, Intent
from channel.builtin import build_registry
from channel.machine import ChannelMachine
from channel.registry import ChannelRegistry
from channel.router import CLARIFY_REPLY, route
from channel.service import ChannelService
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from hal.factory import create_hal
from planner.timeutil import tz_for
from service.app import create_app
from service.config import (
    AppSettings,
    DataSettings,
    HalSettings,
    LoggingSettings,
    SchedulerSettings,
    Settings,
    UiSettings,
)


def make_settings(root: Path) -> Settings:
    identifier = uuid.uuid4().hex
    return Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=root,
            db_path=root / f"channel-{identifier}.db",
            backup_dir=root / f"backup-{identifier}",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )


class BadEnter(BaseChannel):
    key = "bad_enter"
    title = "坏通道"

    def enter(self, ctx, args=None):
        raise RuntimeError("boom")


class BadHandle(BaseChannel):
    key = "bad_handle"
    title = "坏处理"

    def enter(self, ctx, args=None):
        self.ctx = ctx
        return self._finish({})

    def handle(self, intent):
        raise RuntimeError("boom")


def make_machine(
    *,
    switch_limit: int = 12,
    clock=None,
) -> tuple[ChannelMachine, LocalEventBus]:
    bus = LocalEventBus()
    machine = ChannelMachine(
        build_registry(),
        ChannelContext(
            user_id="u_a",
            now=lambda: datetime(2026, 11, 7, 19, 0,
                                 tzinfo=tz_for("Asia/Shanghai")),
        ),
        publisher=bus,
        switch_limit=switch_limit,
        clock=clock,
    )
    return machine, bus


def test_builtin_registry_has_six_channels():
    registry = build_registry()
    assert registry.keys() == [
        "clock",
        "tasks",
        "plan",
        "focus",
        "reminder",
        "music",
    ]
    assert len(registry.list()) == 6


def test_activate_switches_and_return_stack():
    machine, bus = make_machine()
    entered: list[str] = []
    exited: list[str] = []
    bus.subscribe("channel.enter", lambda p: entered.append(p["channel"]))
    bus.subscribe("channel.exit", lambda p: exited.append(str(p["channel"])))
    assert machine.snapshot()["channel"] == "idle"
    clock = machine.activate("clock")
    assert clock["channel"] == "clock"
    tasks = machine.activate("tasks")
    assert tasks["channel"] == "tasks"
    assert exited == ["clock"]
    assert entered == ["clock", "tasks"]
    assert machine.stack_keys == ["clock"]
    back = machine.back()
    assert back["channel"] == "clock"
    assert machine.current_key == "clock"


def test_stack_is_capped_at_three():
    machine, _ = make_machine()
    for key in ("clock", "tasks", "plan", "focus"):
        machine.activate(key)
    assert len(machine.stack_keys) == 3
    assert machine.stack_keys == ["clock", "tasks", "plan"]
    assert machine.back()["channel"] == "plan"


def test_handler_exception_returns_to_idle():
    bus = LocalEventBus()
    registry = ChannelRegistry()
    registry.register(BadHandle())
    machine = ChannelMachine(
        registry,
        ChannelContext(),
        publisher=bus,
    )
    machine.activate("bad_handle")
    actions = machine.handle_intent(Intent("start"))
    assert machine.snapshot()["channel"] == "idle"
    assert any(action.type == "speak" for action in actions)


def test_enter_exception_stays_idle():
    bus = LocalEventBus()
    registry = ChannelRegistry()
    registry.register(BadEnter())
    machine = ChannelMachine(
        registry,
        ChannelContext(),
        publisher=bus,
    )
    snapshot = machine.activate("bad_enter")
    assert snapshot["channel"] == "idle"
    assert machine.current_key is None


def test_overload_after_twelve_switches():
    now = [0.0]
    machine, _ = make_machine(switch_limit=12, clock=lambda: now[0])
    for index in range(12):
        machine.activate("clock" if index % 2 == 0 else "tasks")
        now[0] += 1
    assert machine.overloaded is True
    snapshot = machine.activate("plan")
    assert any("切换" in hint for hint in snapshot["hints"])


def test_router_tool_aliases_and_ambiguity():
    intent = route("帮我打开专注计时器 25 分钟")
    assert intent.name == "open_tool"
    assert intent.tool == "focus"
    assert intent.args["minutes"] == 25
    assert route("看下任务清单").tool == "tasks"
    assert route("打开那个").name == "clarify"
    assert route("打开那个").args["reply"] == CLARIFY_REPLY
    assert route("完全不懂").name == "unknown"
    assert route("返回主页").name == "back"


def test_focus_channel_tick_and_pause():
    machine, _ = make_machine()
    snapshot = machine.activate("focus", {"minutes": 1})
    assert snapshot["data"]["remaining_seconds"] == 60
    machine.handle_intent(Intent("start"))
    machine.tick()
    assert machine.snapshot()["data"]["remaining_seconds"] == 59
    machine.handle_intent(Intent("pause"))
    machine.tick()
    assert machine.snapshot()["data"]["remaining_seconds"] == 59


def test_channel_service_processes_speech_final_and_ticks():
    machine, bus = make_machine()
    service = ChannelService(machine, publisher=bus, subscriber=bus)
    try:
        assert service.start().state == "ok"
        actions = service.handle_text("打开任务清单")
        assert actions
        assert machine.snapshot()["channel"] == "tasks"
        assert service.health().state == "ok"
        bus.publish("speech.final", {"text": "播放音乐"})
        assert machine.snapshot()["channel"] == "music"
    finally:
        service.stop()
    assert service.health().state == "error"


def test_channel_api_and_intent_route(workspace_tmp):
    root = workspace_tmp / f"channel-{uuid.uuid4().hex}"
    settings = Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=root,
            db_path=root / "flow.db",
            backup_dir=root / "backup",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )
    app = create_app(settings, hal=create_hal("mock"))
    with TestClient(app) as client:
        current = client.get("/api/channel/current")
        assert current.status_code == 200
        assert current.json()["channel"] == "idle"
        response = client.post(
            "/api/intent",
            json={"text": "打开专注计时器 10 分钟"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["channel"]["channel"] == "focus"
        assert body["channel"]["data"]["remaining_seconds"] == 600
        assert body["intent"]["tool"] == "focus"
        assert any(
            action["type"] == "channel.snapshot"
            for action in body["actions"]
        )
        again = client.get("/api/channel/current").json()
        assert again["channel"] == "focus"


def test_api_intent_rejects_empty_text(workspace_tmp):
    root = workspace_tmp / f"channel-empty-{uuid.uuid4().hex}"
    settings = make_settings(root)
    app = create_app(settings, hal=create_hal("mock"))
    with TestClient(app) as client:
        response = client.post("/api/intent", json={"text": ""})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_router_priority_table():
    """Order matters, so pin the pairs that used to collide.

    「开始写论文」 opened a timer because a bare 开始 was a global control
    verb; 「太难了不想做了」 became a task because it contains 做.
    """
    cases = {
        "开始写论文": ("make_plan", None),
        "开始": ("start", None),
        "开始专注 5 分钟": ("start", None),
        "我要专注25分钟": ("start", None),
        "太难了不想做了": ("discourage", None),
        "太难了，帮我打开任务清单": ("open_tool", "tasks"),
        "跳过这一步": ("skip", None),
        "再给我十分钟": ("extend", None),
        "还剩多久": ("status", None),
        "我回来了": ("return", None),
        "换小一点": ("split", None),
        "背单词": ("make_plan", None),
    }
    for text, (name, tool) in cases.items():
        intent = route(text)
        assert intent.name == name, text
        assert intent.tool == tool, text
    assert route("再给我十分钟").args["minutes"] == 10
    assert route("再来五分钟").args["minutes"] == 5
    assert route("我要专注半小时").args["minutes"] == 30
