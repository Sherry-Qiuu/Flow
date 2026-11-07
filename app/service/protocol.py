"""Transport protocol models and constants (T03)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

STATE_SYNC = "state.sync"
UI_PHASE = "ui.phase"
ASSISTANT_SAY = "assistant.say"
TASK_CREATED = "task.created"
PLAN_DRAFT = "plan.draft"
REMINDER_FIRED = "reminder.fired"
PHONE_CHANGED = "phone.changed"
REWARD_EVENT = "reward.event"
ERROR = "error"
USER_INTENT = "user.intent"
UI_ACTION = "ui.action"
FOCUS_CONTROL = "focus.control"

CLIENT_MESSAGE_TYPES = frozenset(
    {USER_INTENT, UI_ACTION, FOCUS_CONTROL}
)
SERVER_MESSAGE_TYPES = frozenset(
    {
        STATE_SYNC,
        UI_PHASE,
        ASSISTANT_SAY,
        TASK_CREATED,
        PLAN_DRAFT,
        REMINDER_FIRED,
        PHONE_CHANGED,
        REWARD_EVENT,
        ERROR,
    }
)

ERROR_INVALID_JSON = "invalid_json"
ERROR_INVALID_MESSAGE = "invalid_message"
ERROR_UNKNOWN_TYPE = "unknown_type"
ERROR_INTERNAL = "internal_error"


class ClientMessage(BaseModel):
    """Client -> server message; unknown extra fields are tolerated."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    seq: int | None = None
    ts: str | None = None


class ServerMessage(BaseModel):
    """Server -> client envelope, used by tests and clients."""

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    seq: int = Field(ge=1)
    ts: str


class ErrorPayload(BaseModel):
    code: str
    message: str


def parse_client_message(raw: str) -> ClientMessage:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("message root must be a JSON object")
    return ClientMessage.model_validate(data)
