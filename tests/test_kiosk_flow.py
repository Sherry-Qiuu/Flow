"""Kiosk flow regressions: one timer, one publisher, a reachable plan path."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from channel.base import ChannelContext
from channel.builtin.focus import FocusChannel
from hal.factory import create_hal
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


def make_client(root: Path) -> TestClient:
    identifier = uuid.uuid4().hex
    settings = Settings(
        app=AppSettings(version="flow-test"),
        data=DataSettings(
            dir=root / f"flow-{identifier}",
            db_path=root / f"flow-{identifier}.db",
            backup_dir=root / f"flow-{identifier}-backup",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )
    return TestClient(create_app(settings, hal=create_hal("mock")))


class FrameReader:
    """Collect websocket frames on a thread so tests never block."""

    def __init__(self, websocket) -> None:
        self.frames: queue.Queue[dict] = queue.Queue()
        self.thread = threading.Thread(target=self._run, args=(websocket,))
        self.thread.daemon = True
        self.thread.start()

    def _run(self, websocket) -> None:
        while True:
            try:
                self.frames.put(websocket.receive_json())
            except Exception:
                return

    def drain(self, seconds: float = 1.2) -> list[dict]:
        collected = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                collected.append(self.frames.get(timeout=0.2))
            except queue.Empty:
                continue
        return collected


def test_start_focus_from_idle_starts_the_timer(workspace_tmp):
    """One sentence, one action: no second "开始" required."""
    client = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            reader = FrameReader(websocket)
            reader.drain(0.4)
            intent = client.post(
                "/api/intent",
                json={"text": "开始专注 5 分钟"},
            ).json()["intent"]
            assert intent["name"] == "start"
            focus = client.get("/api/focus").json()
            assert focus["status"] == "running"
            assert focus["total_ms"] == 5 * 60 * 1000
            frames = reader.drain(1.2)
            kinds = [frame["type"] for frame in frames]
            assert "channel.enter" in kinds
            states = [
                frame["payload"]
                for frame in frames
                if frame["type"] == "focus.state"
            ]
            assert states, "the kiosk never learned the timer started"
            assert all(state["status"] == "running" for state in states)
            # A single producer: every frame carries the service snapshot,
            # never the channel's old remaining_seconds-only shape.
            assert all("remaining_ms" in state for state in states)


def test_channel_does_not_publish_its_own_timer(workspace_tmp):
    """With FocusService wired the channel must stay silent between ticks."""
    client = make_client(workspace_tmp)
    with client:
        runtime = client.app.state.runtime
        channel = FocusChannel()
        channel.enter(
            ChannelContext(repos=runtime.repos, focus=runtime.focus),
            {"minutes": 10},
        )
        assert channel.tick(runtime.focus.now_fn()) == []
        actions = channel.handle(_intent("start"))
        assert [action.type for action in actions] == ["speak"]
        assert runtime.focus.snapshot()["status"] == "running"
        assert runtime.focus.snapshot()["remaining_ms"] == 10 * 60 * 1000


def _intent(name: str):
    from channel.base import Intent

    return Intent(name)


def test_confirming_a_plan_without_the_channel_still_shows_executing(workspace_tmp):
    """A running session must win the phase even with an empty channel stack."""
    client = make_client(workspace_tmp)
    with client:
        client.post("/api/demo/reset")
        plan_id = client.post("/api/plan", json={"task_ids": []}).json()["plan_id"]
        client.post(f"/api/plan/{plan_id}/confirm")
        status = client.get("/api/system/status").json()
        assert status["phase"] == "executing"
        assert status["step"]["task_id"] == plan_id
        client.post("/api/focus/control", json={"action": "pause"})
        paused = client.get("/api/system/status").json()
        assert paused["phase"] == "executing"
        assert paused["step"]["status"] == "paused"


def test_unconfirmed_draft_plan_restores_the_review_page(workspace_tmp):
    client = make_client(workspace_tmp)
    with client:
        client.post("/api/demo/reset")
        plan = client.post("/api/plan", json={"task_ids": []}).json()
        status = client.get("/api/system/status").json()
        assert status["phase"] == "plan_review"
        assert status["plan"]["plan_id"] == plan["plan_id"]
        assert status["plan"]["items"]


def test_voice_can_ask_for_a_plan(workspace_tmp):
    """No REST call required: "帮我安排今天" drafts a plan and shows it."""
    client = make_client(workspace_tmp)
    with client:
        client.post("/api/demo/reset")
        with client.websocket_connect("/ws") as websocket:
            reader = FrameReader(websocket)
            reader.drain(0.4)
            intent = client.post(
                "/api/intent",
                json={"text": "帮我安排今天"},
            ).json()["intent"]
            assert intent["name"] == "make_plan"
            frames = reader.drain(1.5)
        drafts = [
            frame["payload"]
            for frame in frames
            if frame["type"] == "plan.draft"
        ]
        assert drafts, "plan.draft never reached the screen"
        assert drafts[0]["items"]
        assert client.get("/api/system/status").json()["phase"] == "plan_review"


def test_planless_timer_finishes_without_touching_plan_items(workspace_tmp):
    client = make_client(workspace_tmp)
    with client:
        client.post("/api/intent", json={"text": "开始专注 5 分钟"})
        result = client.post(
            "/api/focus/control",
            json={"action": "finish"},
        ).json()
        assert result["ok"] is True
        assert result["done"] is True
        assert client.get("/api/focus").json()["status"] == "idle"


def test_wanting_to_focus_hands_over_a_running_timer(workspace_tmp):
    """README promise: 「我要专注 25 分钟」 gives a timer, not a menu."""
    from channel.router import route

    intent = route("我要专注 25 分钟")
    assert intent.name == "start"
    assert intent.args == {"open_focus": True, "minutes": 25}

    client = make_client(workspace_tmp)
    with client:
        client.post("/api/intent", json={"text": "我要专注 25 分钟"})
        focus = client.get("/api/focus").json()
        assert focus["status"] == "running"
        assert focus["total_ms"] == 25 * 60 * 1000
        assert client.get("/api/system/status").json()["phase"] == "executing"
