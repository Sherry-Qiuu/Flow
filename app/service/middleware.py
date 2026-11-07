"""HTTP trace id and access logging middleware."""

from __future__ import annotations

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from service.logging import (
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)

logger = logging.getLogger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("X-Trace-ID")
        trace_id = incoming or new_trace_id()
        token = set_trace_id(trace_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - started) * 1000.0
            response.headers["X-Trace-ID"] = trace_id
            logger.info(
                "http.request",
                extra={
                    "event": "http.request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return response
        finally:
            reset_trace_id(token)
