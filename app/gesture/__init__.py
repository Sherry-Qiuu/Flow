"""Flow gesture and presence detection (T09)."""

from gesture.config import GestureSettings
from gesture.detector import (
    ACTION_MAP,
    GestureDetector,
    GestureEvent,
    normalize_gesture,
)
from gesture.presence import PresenceDetector, PresenceState
from gesture.service import GestureHealth, GestureService

__all__ = [
    "ACTION_MAP",
    "GestureDetector",
    "GestureEvent",
    "GestureHealth",
    "GestureService",
    "GestureSettings",
    "PresenceDetector",
    "PresenceState",
    "normalize_gesture",
]
