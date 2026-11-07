"""T15 reminder model, engine and API tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from bus.local import LocalEventBus
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from hal.factory import create_hal
from planner.timeutil import tz_for
from scheduler.engine import ReminderScheduler
from scheduler.model import ReminderSpec, parse_reminder_text
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
        self.calls: list[tuple[str, str, str]] = []

    def say(self, text, emotion="neutral", priority="normal", **_):
        self.calls.append((text, emotion, priority))


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"rem-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_parse_reminder_kinds():
    now = datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    daily = parse_reminder_text("每天 7 点提醒我背单词", now)
    assert daily.kind == "daily"
    assert daily.at == "07:00"
    assert "背单词" in daily.template
    weekly = parse_reminder_text("每周三 19:30 提醒我跑步", now)
    assert weekly.kind == "weekly"
    assert weekly.weekday == 2
    every = parse_reminder_text("每 45 分钟提醒我站起来", now)
    assert every.kind == "every"
    assert every.minutes == 45
    relative = parse_reminder_text("2 分钟后提醒我喝水", now)
    assert relative.kind == "at"


def test_scheduler_fires_and_disables_one_shot(workspace_tmp):
    database = open_db(workspace_tmp)
    repo = repositories(database.connection, "u_a").reminders
    now = [datetime(2026, 11, 7, 12, 0, tzinfo=TZ)]
    bus = LocalEventBus()
    events = []
    bus.subscribe("reminder.fired", events.append)
    say = FakeSay()
    scheduler = ReminderScheduler(
        repo,
        publisher=bus,
        say=say,
        now_fn=lambda: now[0],
    )
    spec = ReminderSpec(
        kind="at",
        at=(now[0] + timedelta(minutes=1)).isoformat(),
        template="该喝水了",
    )
    reminder_id = scheduler.create(spec)
    assert scheduler.upcoming(24)
    now[0] += timedelta(minutes=2)
    scheduler.tick(now[0])
    assert events
    assert events[0]["title"] == "该喝水了"
    assert say.calls[0][2] == "reminder"
    row = repo.get(reminder_id)
    assert row is not None
    assert row["enabled"] == 0
    database.close()


def test_daily_next_is_tomorrow_after_time():
    now = datetime(2026, 11, 7, 8, 0, tzinfo=TZ)
    spec = ReminderSpec(kind="daily", at="07:00", template="起床")
    next_value = spec.next_after(now)
    assert next_value is not None
    parsed = datetime.fromisoformat(next_value.replace("Z", "+00:00"))
    assert parsed.astimezone(TZ).day == 8


def test_reminder_api(workspace_tmp):
    root = workspace_tmp / f"rem-api-{uuid.uuid4().hex}"
    settings = Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=root,
            db_path=root / "flow.db",
            backup_dir=root / "backup",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=True),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )
    app = create_app(settings, hal=create_hal("mock"))
    with TestClient(app) as client:
        response = client.post(
            "/api/reminders",
            json={"text": "2 分钟后提醒我喝水"},
        )
        assert response.status_code == 200, response.text
        reminder_id = response.json()["id"]
        listed = client.get("/api/reminders").json()
        assert any(item["id"] == reminder_id for item in listed["items"])
        deleted = client.delete(f"/api/reminders/{reminder_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
