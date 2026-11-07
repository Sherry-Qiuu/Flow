"""Barge-in detection and empty-recognition guard."""

from __future__ import annotations

from voice.vad import rms


class EnergyBargeIn:
    def __init__(
        self,
        *,
        threshold: float = 0.03,
        min_frames: int = 2,
    ) -> None:
        self.threshold = threshold
        self.min_frames = max(1, min_frames)
        self._frames = 0

    def feed(self, pcm: bytes) -> bool:
        if rms(pcm) >= self.threshold:
            self._frames += 1
        else:
            self._frames = 0
        if self._frames >= self.min_frames:
            self._frames = 0
            return True
        return False

    def reset(self) -> None:
        self._frames = 0


class EmptyRecognitionGuard:
    def __init__(self, *, limit: int = 3, prompt: str = "") -> None:
        self.limit = max(1, limit)
        self.prompt = prompt or "没听清，可以说慢一点"
        self._empty = 0

    @property
    def count(self) -> int:
        return self._empty

    def record(self, text: str) -> str | None:
        if text.strip():
            self._empty = 0
            return None
        self._empty += 1
        if self._empty >= self.limit:
            self._empty = 0
            return self.prompt
        return None

    def reset(self) -> None:
        self._empty = 0
