"""T03 REST / health tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hal.factory import create_hal
from service.app import create_app, ensure_single_worker
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
            # The focus store lives under data.dir; a shared dir would leak a
            # running session from one test into the next.
            dir=root / f"api-{identifier}",
            db_path=root / f"api-{identifier}.db",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )


def make_client(root: Path):
    settings = make_settings(root)
    app = create_app(settings, hal=create_hal("mock"))
    return TestClient(app), app


def test_healthz_returns_version_uptime_and_subsystems(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "test-version"
    assert payload["status"] == "ok"
    assert payload["started_at"]
    assert payload["uptime_s"] >= 0
    assert set(payload["subsystems"]) == {
        "db",
        "hal",
        "scheduler",
        "channel",
        "phone",
        "voice",
        "websocket",
    }
    assert payload["subsystems"]["db"]["state"] == "ok"
    assert payload["subsystems"]["hal"]["state"] == "ok"
    assert payload["subsystems"]["phone"]["state"] == "ok"
    assert payload["subsystems"]["voice"]["state"] == "disabled"


def test_trace_header_is_echoed_and_generated(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        supplied = client.get(
            "/healthz",
            headers={"X-Trace-ID": "trace-from-client"},
        )
        generated = client.get("/healthz")
    assert supplied.headers["X-Trace-ID"] == "trace-from-client"
    assert generated.headers["X-Trace-ID"]
    assert generated.headers["X-Trace-ID"] != "trace-from-client"


def test_system_status_contains_runtime_state(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "idle"
    # Mirrors the channel machine: nothing is active, so the channel is idle.
    assert payload["channel"] == "idle"
    assert payload["tasks_count"] == 0
    assert "phone" in payload
    assert "hal" in payload


def test_index_placeholder_renders(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        response = client.get("/")
    assert response.status_code == 200
    assert "心流 Flow" in response.text


def test_unknown_route_uses_uniform_error(workspace_tmp):
    client, _ = make_client(workspace_tmp)
    with client:
        response = client.get("/api/nope/missing")
    assert response.status_code == 404
    payload = response.json()
    assert set(payload["error"]) == {"code", "message", "trace_id"}


def test_ensure_single_worker_rejects_multi_worker():
    ensure_single_worker({"WEB_CONCURRENCY": "1"})
    with pytest.raises(RuntimeError, match="single uvicorn worker"):
        ensure_single_worker({"WEB_CONCURRENCY": "2"})


def test_single_worker_config_is_enforced_and_not_just_documented(
    workspace_tmp,
):
    """app.single_worker used to be read by nobody."""
    from dataclasses import replace

    settings = make_settings(workspace_tmp)
    configured = replace(
        settings,
        app=replace(settings.app, single_worker=False),
    )
    with pytest.raises(RuntimeError, match="single_worker"):
        create_app(configured, hal=create_hal("mock"))


def test_health_degrades_when_camera_is_missing(workspace_tmp):
    settings = make_settings(workspace_tmp)
    hal = create_hal("mock")
    hal.camera.unplug()
    app = create_app(settings, hal=hal)
    with TestClient(app) as client:
        payload = client.get("/healthz").json()
    assert payload["status"] == "degraded"
    assert payload["subsystems"]["hal"]["state"] == "degraded"
    assert "camera" in payload["hal_faults"]
