"""T21 phone usage contract tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from bus.local import LocalEventBus
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from hal.factory import create_hal
from phone.contract import PhoneContractService
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

TZ = tz_for("Asia/Shanghai")


class FakeSay:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def say(self, text, **_):
        self.calls.append(text)


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"contract-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_study_contract_extend_and_return(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    now = [datetime(2026, 11, 7, 12, 0, tzinfo=TZ)]
    bus = LocalEventBus()
    events: list[dict] = []
    bus.subscribe("phone.session.started", events.append)
    say = FakeSay()
    service = PhoneContractService(
        repo,
        publisher=bus,
        say=say,
        now_fn=lambda: now[0],
    )
    service.start()
    try:
        contract = service.begin("study", 10)
        assert contract.planned_minutes == 10
        assert events
        assert service.extend(5) is True
        assert service.extend(5) is False
        assert (
            service.snapshot()["contract"]["data"]["remaining_seconds"]
            == 900
        )
        now[0] += timedelta(minutes=1)
        assert service.end("manual") is True
        assert repo.open_session() is None
        assert say.calls
    finally:
        service.stop()
        database.close()


def test_leisure_cannot_extend_and_overdue_reminds(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    now = [datetime(2026, 11, 7, 12, 0, tzinfo=TZ)]
    bus = LocalEventBus()
    overdue = []
    bus.subscribe("phone.session.overdue", overdue.append)
    service = PhoneContractService(
        repo,
        publisher=bus,
        now_fn=lambda: now[0],
    )
    service.start()
    try:
        service.begin("leisure", 10)
        assert service.extend(5) is False
        now[0] += timedelta(minutes=11)
        service.tick(now[0])
        assert overdue
        assert service.active is not None
        assert service.active.status == "overdue"
        service.end("manual")
    finally:
        service.stop()
        database.close()


def test_phone_return_event_ends_contract(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").phone_sessions
    now = datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    bus = LocalEventBus()
    service = PhoneContractService(
        repo,
        publisher=bus,
        subscriber=bus,
        now_fn=lambda: now,
    )
    service.start()
    try:
        service.begin("study", 5)
        bus.publish("phone.changed", {"present": True, "charging": True})
        assert service.active is None
    finally:
        service.stop()
        database.close()


def test_phone_contract_api(workspace_tmp):
    root = workspace_tmp / f"contract-api-{uuid.uuid4().hex}"
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
        started = client.post(
            "/api/phone/session",
            json={"purpose": "study", "minutes": 10},
        )
        assert started.status_code == 200, started.text
        assert started.json()["active"] is True
        extended = client.post(
            "/api/phone/session/extend",
            json={"minutes": 5},
        )
        assert extended.json()["extended"] is True
        ended = client.post("/api/phone/session/end")
        assert ended.json()["ended"] is True
