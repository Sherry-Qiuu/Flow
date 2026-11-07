"""Structured logging tests."""

from __future__ import annotations

import io
import json
import logging

from service.logging import (
    JsonFormatter,
    configure_logging,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)


def test_json_formatter_contains_trace_id_and_extra():
    token = set_trace_id("trace-123")
    try:
        record = logging.LogRecord(
            "flow.test",
            logging.INFO,
            __file__,
            10,
            "hello %s",
            ("world",),
            None,
        )
        record.event = "unit.test"
        payload = json.loads(JsonFormatter().format(record))
        assert payload["message"] == "hello world"
        assert payload["trace_id"] == "trace-123"
        assert payload["event"] == "unit.test"
        assert payload["level"] == "INFO"
    finally:
        reset_trace_id(token)


def test_new_trace_id_is_unique():
    assert new_trace_id() != new_trace_id()


def test_configure_logging_emits_one_json_line():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    stream = io.StringIO()
    try:
        configure_logging("INFO", json_mode=True, stream=stream)
        logging.getLogger("flow.test").info("service ready")
        lines = [line for line in stream.getvalue().splitlines() if line]
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["message"] == "service ready"
    finally:
        root.handlers.clear()
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)
