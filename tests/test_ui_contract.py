"""Guard the TypeScript client against protocol drift (no Node required)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from channel.builtin import build_registry
from hal.factory import create_hal
from service import protocol
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

UI = Path(__file__).resolve().parents[1] / "ui" / "src"


def _read(*parts: str) -> str:
    return (UI.joinpath(*parts)).read_text(encoding="utf-8")


def test_every_event_the_reducer_handles_is_declared_server_side():
    body = _read("state", "reducer.ts")
    # Only the websocket dispatch counts; the outer switch also handles
    # local actions such as "clock" and "connection".
    segment = body[body.index("function applyMessage"):]
    end = segment.find("\n}\n")
    if end != -1:
        segment = segment[:end]
    handled = {
        name
        for name in re.findall(r'case "([a-z_.]+)":', segment)
        if name != "default"
    }
    assert handled, "reducer handles no message types"
    undeclared = handled - protocol.SERVER_MESSAGE_TYPES
    assert not undeclared, (
        "the UI handles events the server never declares: "
        f"{sorted(undeclared)}"
    )


def test_every_channel_is_displayable():
    body = _read("state", "types.ts")
    block = re.search(
        r"export type Channel\s*=\s*(.*?);",
        body,
        re.S,
    )
    assert block is not None, "Channel union not found"
    known = set(re.findall(r'"([a-z_]+)"', block.group(1)))
    keys = set(build_registry().keys()) | {"idle"}
    missing = keys - known
    assert not missing, f"channels the UI cannot render: {sorted(missing)}"


def test_every_client_message_type_has_a_handler(workspace_tmp):
    settings = Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=workspace_tmp,
            db_path=workspace_tmp / f"contract-{uuid.uuid4().hex}.db",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(),
    )
    app = create_app(settings, hal=create_hal("mock"))
    client = TestClient(app)
    with client:
        registered = set(app.state.runtime.hub._handlers)
    unhandled = protocol.CLIENT_MESSAGE_TYPES - registered
    assert not unhandled, (
        "the client can send these, but the server drops them: "
        f"{sorted(unhandled)}"
    )


def test_state_sync_carries_what_the_reducer_reads(workspace_tmp):
    """The reducer falls back to placeholder copy for missing keys."""
    settings = Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=workspace_tmp,
            db_path=workspace_tmp / f"sync-{uuid.uuid4().hex}.db",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(),
    )
    app = create_app(settings, hal=create_hal("mock"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            payload = websocket.receive_json()["payload"]
    for key in ("phase", "channel", "channel_state", "message", "tasks_count"):
        assert key in payload, f"state.sync is missing {key}"
