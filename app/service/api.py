"""REST routes and uniform error handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from service.logging import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter()

_PLACEHOLDER = Path(__file__).with_name("placeholder.html")


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": get_trace_id(),
        }
    }


@router.get("/healthz")
def healthz(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError(
            "not_ready",
            "service runtime is not initialized",
            503,
        )
    return runtime.health_payload()


@router.get("/api/system/status")
def system_status(request: Request) -> dict[str, Any]:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise ApiError(
            "not_ready",
            "service runtime is not initialized",
            503,
        )
    return runtime.snapshot()


def placeholder_html() -> str:
    if _PLACEHOLDER.exists():
        return _PLACEHOLDER.read_text(encoding="utf-8")
    return "<h1>Flow</h1>"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(
        request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "validation_error",
                "request validation failed",
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else "request failed"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload("http_error", message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "unhandled request error",
            extra={
                "event": "http.error",
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "internal_error",
                "internal server error",
            ),
        )
