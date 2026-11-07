"""Boot a real uvicorn server once and talk HTTP to it.

``TestClient`` drives the ASGI app in-process and can hide routing or
lifespan problems that only show up behind a real socket (FastAPI 0.16x
moved ``include_router`` to a lazily built dispatch table). The Pi never
runs TestClient, so at least one test has to cross a socket.
"""

from __future__ import annotations

import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn

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


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_real_server_serves_the_api(workspace_tmp):
    identifier = uuid.uuid4().hex
    settings = Settings(
        app=AppSettings(version="live"),
        data=DataSettings(
            dir=workspace_tmp / f"live-{identifier}",
            db_path=workspace_tmp / f"live-{identifier}.db",
            backup_dir=workspace_tmp / f"live-{identifier}-backup",
        ),
        hal=HalSettings(backend="mock"),
        scheduler=SchedulerSettings(enabled=False),
        logging=LoggingSettings(level="CRITICAL", json=True),
        ui=UiSettings(size="720x720"),
    )
    app = create_app(settings, hal=create_hal("mock"))
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="critical",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 30
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                response = httpx.get(f"{base}/healthz", timeout=2, trust_env=False)
            except Exception as exc:  # noqa: BLE001 - server may not be up yet
                last_error = exc
                time.sleep(0.2)
                continue
            assert response.status_code == 200, response.text
            break
        else:  # pragma: no cover - only when the server never came up
            pytest.fail(f"server did not start: {last_error}")

        # A route that lives on the included router, not on the app itself.
        status = httpx.get(
            f"{base}/api/system/status", timeout=5, trust_env=False
        ).json()
        assert status["phase"] == "idle"
        intent = httpx.post(
            f"{base}/api/intent",
            json={"text": "打开任务清单"},
            timeout=5,
            trust_env=False,
        ).json()
        assert intent["intent"]["name"] == "open_tool"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
