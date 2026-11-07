"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from bus.event_bus import EventBus
from hal.factory import Hal
from service.api import (
    install_exception_handlers,
    placeholder_html,
    router,
)
from service.config import Settings, load_settings
from service.middleware import TraceIdMiddleware
from service.runtime import Runtime
from service.ui_static import find_ui_dist


def ensure_single_worker(env: dict[str, str] | None = None) -> None:
    """Reject multi-worker deployments; bus and scheduler are in-process."""
    values = os.environ if env is None else env
    raw = values.get("WEB_CONCURRENCY") or values.get("UVICORN_WORKERS")
    if raw is None or str(raw).strip() == "":
        return
    try:
        workers = int(str(raw).strip())
    except ValueError:
        raise RuntimeError("worker count must be an integer") from None
    if workers > 1:
        raise RuntimeError(
            "Flow requires a single uvicorn worker; "
            "multi-worker would duplicate the event bus and scheduler"
        )


def create_app(
    settings: Settings | None = None,
    *,
    event_bus: EventBus | None = None,
    hal: Hal | None = None,
) -> FastAPI:
    ensure_single_worker()
    resolved = settings or load_settings()
    runtime = Runtime(resolved, event_bus, hal)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="Flow",
        version=resolved.app.version,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.runtime = runtime
    app.add_middleware(TraceIdMiddleware)
    app.include_router(router)
    install_exception_handlers(app)

    ui_dist = find_ui_dist()
    app.state.ui_dist = ui_dist
    if ui_dist is not None:
        assets = ui_dist / "assets"
        if assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets)),
                name="ui-assets",
            )

        @app.get("/", include_in_schema=False)
        def ui_index() -> FileResponse:
            return FileResponse(ui_dist / "index.html")

        favicon = ui_dist / "favicon.svg"
        if favicon.is_file():

            @app.get("/favicon.svg", include_in_schema=False)
            def ui_favicon() -> FileResponse:
                return FileResponse(favicon)

    else:

        @app.get("/", response_class=HTMLResponse)
        def placeholder_index() -> str:
            return placeholder_html()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await runtime.hub.handle_connection(websocket)

    return app
