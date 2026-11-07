"""API smoke for the remaining P1/P2 surfaces."""

from __future__ import annotations

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


def make_client(root: Path) -> TestClient:
    settings = Settings(
        app=AppSettings(version="api-remaining"),
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
    return TestClient(create_app(settings, hal=create_hal("mock")))


def test_remaining_api_smoke(workspace_tmp):
    root = workspace_tmp / f"remaining-api-{uuid.uuid4().hex}"
    with make_client(root) as client:
        created = client.post(
            "/api/users",
            json={"name": "小 B", "nickname": "B"},
        )
        assert created.status_code == 200, created.text
        user_id = created.json()["id"]
        switched = client.post(f"/api/users/{user_id}/switch")
        assert switched.status_code == 200
        prefs = client.put(
            "/api/prefs",
            json={"values": {"theme": "cool", "voice": "zh"}},
        )
        assert prefs.status_code == 200
        assert prefs.json()["theme"] == "cool"

        uploaded = client.post(
            "/api/files",
            content=b"%PDF-1.4 test",
            headers={"X-Filename": "notes.pdf"},
        )
        assert uploaded.status_code == 200, uploaded.text
        files = client.get("/api/files").json()
        assert files["items"]

        usage = client.get("/api/phone/usage").json()
        assert usage["enabled"] is False
        toggled = client.post(
            "/api/phone/usage/toggle",
            json={"enabled": True},
        )
        assert toggled.json()["enabled"] is True
        ingested = client.post(
            "/api/phone/usage",
            json={"packages": {"com.example": 12}},
        )
        assert ingested.json()["accepted"] is True

        distraction = client.post(
            "/api/distraction",
            json={"minutes": 8, "purpose": "leisure", "context": "卡住"},
        )
        assert distraction.status_code == 200
        insights = client.get("/api/insights/distraction?range=7d")
        assert insights.status_code == 200
        assert insights.json()["count"] >= 1

        assert client.get("/api/load").status_code == 200
        assert client.get("/api/metrics?range=7d").status_code == 200
        weekly = client.get("/api/weekly")
        assert weekly.status_code == 200
        assert len(weekly.json()["cards"]) == 3
        assert client.get("/api/degrade").status_code == 200
        assert client.get("/api/recovery").status_code == 200

        dialogue = client.post(
            "/api/dialogue",
            json={"text": "打开任务清单"},
        )
        assert dialogue.status_code == 200
        assert dialogue.json()["actions"][0]["kind"] == "enter_channel"

        celebration = client.post(
            "/api/celebrate",
            json={"kind": "step_done"},
        )
        assert celebration.status_code == 200
        assert client.get("/api/companion").status_code == 200

        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
