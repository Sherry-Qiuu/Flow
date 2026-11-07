"""T03 WebSocket protocol tests."""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

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
from service.protocol import ServerMessage


def make_client(root: Path):
    settings = Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=root,
            db_path=root / f"ws-{uuid.uuid4().hex}.db",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(),
    )
    app = create_app(settings, hal=create_hal("mock"))
    return TestClient(app), app


def test_connect_receives_state_sync_within_ten_seconds(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        started = time.monotonic()
        with client.websocket_connect("/ws") as websocket:
            payload = websocket.receive_json()
        elapsed = time.monotonic() - started
    assert elapsed < 10
    assert payload["type"] == "state.sync"
    assert payload["seq"] >= 1
    assert payload["ts"].endswith("Z")
    ServerMessage.model_validate(payload)
    assert payload["payload"]["phase"] == "idle"
    assert "hal" in payload["payload"]
    assert "phone" in payload["payload"]


def _drain_until(websocket, wanted: str, limit: int = 12):
    seen: list[str] = []
    for _ in range(limit):
        message = websocket.receive_json()
        seen.append(message["type"])
        if message["type"] == wanted:
            return message
    raise AssertionError(f"{wanted} never arrived; saw {seen}")


def test_invalid_json_returns_error_and_keeps_socket(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_text("{not-json")
            error = websocket.receive_json()
            assert error["type"] == "error"
            assert error["payload"]["code"] == "invalid_json"
            # Still alive, and a rejected action says why instead of hanging.
            websocket.send_json(
                {"type": "ui.action", "payload": {"action": "wave-ish"}}
            )
            rejected = websocket.receive_json()
            assert rejected["type"] == "error"
            assert rejected["payload"]["code"] == "invalid_action"
            websocket.send_json({"type": "nope", "payload": {}})
            unknown = websocket.receive_json()
            assert unknown["payload"]["code"] == "unknown_type"


def test_invalid_message_shape_returns_error(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"payload": {}})
            error = websocket.receive_json()
            assert error["type"] == "error"
            assert error["payload"]["code"] == "invalid_message"


def test_text_intent_over_websocket_enters_a_channel(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "user.intent",
                    "payload": {"text": "打开任务清单"},
                }
            )
            entered = _drain_until(websocket, "channel.enter")
    assert entered["payload"]["channel"] == "tasks"
    assert entered["payload"]["title"] == "任务清单"


def test_touch_action_from_the_client_takes_the_same_path(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {"type": "ui.action", "payload": {"action": "open_tasks"}}
            )
            entered = _drain_until(websocket, "channel.enter")
    assert entered["payload"]["channel"] == "tasks"
    assert entered["payload"]["title"] == "任务清单"


def test_focus_control_starts_the_timer_and_state_sync_agrees(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {"type": "user.intent", "payload": {"text": "开始专注"}}
            )
            entered = _drain_until(websocket, "channel.enter")
            assert entered["payload"]["channel"] == "focus"
            websocket.send_json(
                {"type": "focus.control", "payload": {"action": "start"}}
            )
            state = _drain_until(websocket, "focus.state")
            assert state["payload"]["running"] is True
        # Reconnect must not claim idle while the timer is running.
        with client.websocket_connect("/ws") as websocket:
            synced = websocket.receive_json()["payload"]
            assert synced["phase"] == "executing"
            assert synced["channel"] == "focus"
            assert synced["message"]
            # "speak" used to be dropped; it now reaches the screen as copy.
            websocket.send_json(
                {"type": "ui.action", "payload": {"action": "finish"}}
            )
            said = _drain_until(websocket, "assistant.say")
            assert said["payload"]["text"]


def test_registered_handler_receives_client_message(workspace_tmp):
    client, app = make_client(workspace_tmp)
    handled = threading.Event()
    received: list[str] = []

    async def on_intent(connection, message):
        del connection
        received.append(message.payload.get("text", ""))
        handled.set()

    runtime = app.state.runtime
    with client:
        # Register after startup: runtime wires its own intent handler there.
        runtime.hub.register_handler("user.intent", on_intent)
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {"type": "user.intent", "payload": {"text": "写论文"}}
            )
            assert handled.wait(2.0)
    assert received == ["写论文"]


def test_bus_event_is_broadcast_to_connected_clients(workspace_tmp):
    client, app = make_client(workspace_tmp)
    with client:
        with client.websocket_connect("/ws") as first:
            first.receive_json()
            with client.websocket_connect("/ws") as second:
                second.receive_json()
                app.state.runtime.bus.publish(
                    "phone.changed",
                    {"present": True, "charging": True},
                )
                first_event = first.receive_json()
                second_event = second.receive_json()
    assert first_event["type"] == "phone.changed"
    assert second_event["type"] == "phone.changed"
    assert first_event["payload"]["present"] is True
