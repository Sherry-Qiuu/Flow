"""Gesture detection and presence interaction (T09)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GestureSettings:
    enabled: bool = True
    approach_cm: float = 60.0
    leave_cm: float = 300.0
    leave_hold_s: float = 60.0
    cooldown_s: float = 1.5
    debounce_frames: int = 5
    min_votes: int = 2
    poll_ms: int = 50

    def __post_init__(self) -> None:
        if self.leave_cm <= self.approach_cm:
            raise ValueError("leave_cm must be greater than approach_cm")
        if self.leave_hold_s < 0:
            raise ValueError("leave_hold_s must be non-negative")
        if self.cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        if not 1 <= self.min_votes <= self.debounce_frames:
            raise ValueError("min_votes must be in 1..debounce_frames")
        if self.poll_ms <= 0:
            raise ValueError("poll_ms must be positive")
