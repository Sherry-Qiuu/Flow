"""Transport protocol models and constants (T03)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

STATE_SYNC = "state.sync"
UI_PHASE = "ui.phase"
ASSISTANT_SAY = "assistant.say"
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
PLAN_DRAFT = "plan.draft"
PLAN_REVISED = "plan.revised"
PLAN_CONFIRMED = "plan.confirmed"
FOCUS_STATE = "focus.state"
CHANNEL_ENTER = "channel.enter"
CHANNEL_EXIT = "channel.exit"
MUSIC_STATE = "music.state"
REMINDER_FIRED = "reminder.fired"
PHONE_CHANGED = "phone.changed"
REWARD_EVENT = "reward.event"
REWARD_FEEDBACK = "reward.feedback"
EMOTION_FACE = "emotion.face"
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
        TASK_UPDATED,
        PLAN_DRAFT,
        PLAN_REVISED,
        PLAN_CONFIRMED,
        FOCUS_STATE,
        CHANNEL_ENTER,
        CHANNEL_EXIT,
        MUSIC_STATE,
        REMINDER_FIRED,
        PHONE_CHANGED,
        REWARD_EVENT,
        REWARD_FEEDBACK,
        EMOTION_FACE,
        ERROR,
    }
)

ERROR_INVALID_JSON = "invalid_json"
ERROR_INVALID_MESSAGE = "invalid_message"
ERROR_UNKNOWN_TYPE = "unknown_type"
ERROR_NO_HANDLER = "no_handler"
ERROR_NOT_READY = "not_ready"
ERROR_INVALID_ACTION = "invalid_action"
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
