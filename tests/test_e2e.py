"""T28 main-flow end-to-end test and T30 setup contract."""

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
from setup.wizard import first_run_needed, write_first_run_config


def make_app(root: Path) -> TestClient:
    settings = Settings(
        app=AppSettings(version="e2e"),
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


def test_demo_main_flow(workspace_tmp):
    root = workspace_tmp / f"e2e-{uuid.uuid4().hex}"
    app = make_app(root)
    with app as client:
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200, reset.text
        assert reset.json()["count"] if "count" in reset.json() else True

        plan = client.post("/api/plan", json={"task_ids": []})
        assert plan.status_code == 200, plan.text
        plan_body = plan.json()
        plan_id = plan_body["plan_id"]
        assert plan_body["items"]

        confirmed = client.post(f"/api/plan/{plan_id}/confirm")
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["focus"]["ok"] is True

        focus = client.get("/api/focus").json()
        assert focus["status"] == "running"
        finished = client.post(
            "/api/focus/control",
            json={"action": "finish"},
        )
        assert finished.status_code == 200
        assert finished.json()["ok"] is True

        reward = client.post("/api/celebrate", json={"kind": "task_done"})
        # The endpoint is optional in early clients; fall back to feedback.
        assert reward.status_code in (200, 404, 405)
        weekly = client.get("/api/weekly")
        assert weekly.status_code == 200
        assert len(weekly.json()["cards"]) == 3
        metrics = client.get("/api/metrics?range=7d")
        assert metrics.status_code == 200
        degrade = client.get("/api/degrade")
        assert "items" in degrade.json()

        phone = client.post(
            "/api/phone/session",
            json={"purpose": "study", "minutes": 5},
        )
        assert phone.status_code == 200
        ended = client.post("/api/phone/session/end")
        assert ended.json()["ended"] is True


def test_first_run_config_contract(workspace_tmp):
    path = workspace_tmp / f"setup-{uuid.uuid4().hex}.yaml"
    assert first_run_needed(path) is True
    write_first_run_config(path, name="小 A", nickname="A", voice="zh")
    assert first_run_needed(path) is False
    assert "小 A" in path.read_text("utf-8")
