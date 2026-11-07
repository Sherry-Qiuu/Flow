"""Structured JSON logging with a request/connection trace id."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("flow_trace_id", default="-")

_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status",
    "duration_ms",
    "device",
    "topic",
    "client_id",
    "message_type",
)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(value: str | None) -> Token:
    return trace_id_var.set(value or new_trace_id())


def reset_trace_id(token: Token) -> None:
    trace_id_var.reset(token)


def get_trace_id() -> str:
    return trace_id_var.get()


class JsonFormatter(logging.Formatter):
    """One JSON object per line; safe for journald."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                record.created,
                timezone.utc,
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": get_trace_id(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(levelname)s [%(trace_id)s] "
            "%(name)s: %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = get_trace_id()
        return super().format(record)


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def configure_logging(
    level: str = "INFO",
    *,
    json_mode: bool = True,
    stream: Any = None,
) -> None:
    """Install one root handler; called once during app startup."""
    target = stream or sys.stdout
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(target)
    handler.setLevel(level.upper())
    if json_mode:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())
    handler.addFilter(TraceIdFilter())
    root.addHandler(handler)

    # Uvicorn installs its own handlers before lifespan startup. Let all
    # service logs flow through the same JSON formatter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
