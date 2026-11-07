"""T20 phone debounce, sessions, service and manual fallback."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from bus.local import LocalEventBus
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from hal.factory import create_hal
from hal.mock import MockPhoneStand
from phone.service import PhoneSessionService
from phone.session_store import PhoneSessionStore, PhoneSnapshot
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


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"phone-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_three_samples_are_required_and_sessions_are_persisted(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    store = PhoneSessionStore(repo)
    assert store.observe(False, False) is None
    assert store.observe(False, False) is None
    assert store.observe(False, False) is None
    assert store.observe(True, True) is None
    assert store.observe(True, True) is None
    transition = store.observe(True, True, current_ma=420, at="t1")
    assert transition is not None
    assert transition.kind == "placed"
    assert transition.snapshot.charging is True
    assert store.session_id is not None
    assert repo.open_session() is not None

    # A single jitter sample must not end the session.
    assert store.observe(False, False) is None
    assert store.observe(True, True) is None
    assert store.observe(True, True) is None
    assert repo.open_session() is not None

    store.observe(False, False)
    store.observe(False, False)
    removed = store.observe(False, False, at="t2")
    assert removed is not None
    assert removed.kind == "removed"
    assert store.session_id is None
    assert repo.open_session() is None
    assert len(repo.list()) == 1
    database.close()


def test_manual_fallback_creates_and_closes_session(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    store = PhoneSessionStore(repo)
    store.seed(PhoneSnapshot())
    placed = store.manual(True, True, current_ma=400, at="m1")
    assert placed is not None
    assert placed.kind == "placed"
    removed = store.manual(False, False, at="m2")
    assert removed is not None
    assert removed.kind == "removed"
    database.close()


def test_service_polls_mock_phone_stand(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    bus = LocalEventBus()
    stand = MockPhoneStand(bus, poll_interval=0.02)
    assert stand.open().available
    service = PhoneSessionService(stand, repo, poll_ms=20)
    try:
        assert service.start().state == "ok"
        stand.place_phone()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and repo.open_session() is None:
            time.sleep(0.03)
        assert repo.open_session() is not None
        stand.remove_phone()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and repo.open_session() is not None:
            time.sleep(0.03)
        assert repo.open_session() is None
        assert len(repo.list()) == 1
        assert service.health().state == "ok"
    finally:
        service.stop()
        stand.close()
        database.close()


def test_service_without_sensor_is_disabled_but_manual_works(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    service = PhoneSessionService(None, repo)
    assert service.start().state == "disabled"
    assert service.health().healthy
    transition = service.manual(True, False)
    assert transition is not None
    assert repo.open_session() is not None
    service.stop()
    database.close()


def test_phone_manual_api(workspace_tmp):
    root = workspace_tmp / f"phone-api-{uuid.uuid4().hex}"
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
        response = client.post(
            "/api/phone/manual",
            json={"present": True, "charging": True, "current_ma": 420},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["phone"]["present"] is True
        assert body["phone"]["charging"] is True
        assert body["phone"]["session_id"]
        status = client.get("/api/system/status").json()
        assert status["phone"]["present"] is True
        assert status["phone"]["charging"] is True
