"""T11 text extraction, dedupe, photo quality and commit tests."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from capture.extract import dedupe_drafts, extract_from_text
from capture.photo import PhotoImporter, check_quality
from capture.service import TaskCaptureService
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from hal.factory import create_hal
from hal.mock import MockCamera
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


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"capture-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_extract_multiple_tasks_and_fields():
    now = datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    drafts = extract_from_text(
        "明天要交物理实验报告，然后背30个单词；写论文 2小时",
        now=now,
    )
    assert len(drafts) == 3
    assert drafts[0].deadline is not None
    assert drafts[0].deadline.day == 8
    assert drafts[0].course == "物理"
    assert drafts[0].priority == "high"
    assert drafts[2].est_minutes == 120


def test_dedupe_and_commit(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    service = TaskCaptureService(repos)
    drafts = service.from_text("明天要交物理实验报告，然后背30个单词")
    assert len(drafts) == 2
    assert drafts[0]["duplicate"] is False
    again = service.from_text("明天要交物理实验报告")
    assert again[0]["duplicate"] is True
    committed = service.commit(
        [
            {
                "title": "写论文",
                "est_minutes": 45,
                "selected": True,
                "source": "voice",
            }
        ]
    )
    assert len(committed) == 1
    assert repos.tasks.get(committed[0].id).source == "voice"
    database.close()


def test_photo_quality_and_fallback_import(workspace_tmp):
    camera = MockCamera()
    importer = PhotoImporter(
        camera,
        inbox=workspace_tmp / f"inbox-{uuid.uuid4().hex}",
    )
    result = importer.capture()
    assert result["ok"] is True
    assert result["drafts"]
    assert Path(result["path"]).is_file()
    assert check_quality(b"too small").ok is False


def test_capture_api(workspace_tmp):
    root = workspace_tmp / f"capture-api-{uuid.uuid4().hex}"
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
        extracted = client.post(
            "/api/capture/text",
            json={"text": "明天交物理报告，然后背30个单词"},
        )
        assert extracted.status_code == 200, extracted.text
        drafts = extracted.json()["drafts"]
        assert len(drafts) == 2
        committed = client.post(
            "/api/capture/commit",
            json={"drafts": drafts},
        )
        assert committed.json()["count"] == 2
        photo = client.post("/api/capture/photo")
        assert photo.status_code == 200
        assert photo.json()["ok"] is True
