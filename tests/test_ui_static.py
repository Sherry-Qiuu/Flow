"""T05 built UI integration with the T03 backend."""

from __future__ import annotations

import re
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

ROOT = Path(__file__).resolve().parents[1]


def make_settings(root: Path) -> Settings:
    return Settings(
        app=AppSettings(version="test-version"),
        data=DataSettings(
            dir=root,
            db_path=root / f"ui-{uuid.uuid4().hex}.db",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )


def test_ui_build_artifact_is_present():
    dist = ROOT / "ui" / "dist"
    index = dist / "index.html"
    assert index.is_file()
    assets = list((dist / "assets").glob("*"))
    assert any(path.suffix == ".js" for path in assets)
    assert any(path.suffix == ".css" for path in assets)


def test_backend_serves_built_ui_and_assets(workspace_tmp):
    app = create_app(make_settings(workspace_tmp), hal=create_hal("mock"))
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "<title>心流 Flow</title>" in index.text
        assert 'id="root"' in index.text

        references = re.findall(
            r'(?:src|href)="(/assets/[^"]+)"',
            index.text,
        )
        assert references
        for reference in references:
            response = client.get(reference)
            assert response.status_code == 200
            assert response.content


def test_placeholder_is_used_when_dist_is_missing(
    workspace_tmp,
    monkeypatch,
):
    import service.app as app_module

    monkeypatch.setattr(app_module, "find_ui_dist", lambda: None)
    app = create_app(make_settings(workspace_tmp), hal=create_hal("mock"))
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "心流 Flow" in response.text
    assert 'id="root"' not in response.text
