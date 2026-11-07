"""16 kHz capture with a three-second pre-roll ring buffer."""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from hal.contracts import AudioFrame, AudioIn, DeviceStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureHealth:
    state: str
    detail: str = ""
    frames: int = 0
    buffered_ms: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "detail": self.detail,
            "frames": self.frames,
            "buffered_ms": round(self.buffered_ms, 1),
        }


class RingBuffer:
    """Keep the most recent audio without unbounded growth."""

    def __init__(self, seconds: float, sample_rate: int = 16000) -> None:
        self.seconds = max(0.0, float(seconds))
        self.sample_rate = sample_rate
        self._frames: deque[bytes] = deque()
        self._duration_ms = 0.0
        self._lock = threading.RLock()

    @property
    def duration_ms(self) -> float:
        with self._lock:
            return self._duration_ms

    @property
    def frames(self) -> int:
        with self._lock:
            return len(self._frames)

    def append(self, pcm: bytes, duration_ms: float) -> None:
        if not pcm:
            return
        with self._lock:
            self._frames.append(pcm)
            self._duration_ms += max(0.0, duration_ms)
            while (
                self._frames
                and self._duration_ms > self.seconds * 1000
            ):
                removed = self._frames.popleft()
                self._duration_ms -= len(removed) * 1000.0 / (
                    self.sample_rate * 2
                )

    def pre_roll(self, seconds: float | None = None) -> bytes:
        limit_ms = (
            self.seconds if seconds is None else max(0.0, seconds)
        ) * 1000
        with self._lock:
            selected: list[bytes] = []
            total = 0.0
            for pcm in reversed(self._frames):
                duration = len(pcm) * 1000.0 / (self.sample_rate * 2)
                if total + duration > limit_ms and selected:
                    break
                selected.append(pcm)
                total += duration
            return b"".join(reversed(selected))

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._duration_ms = 0.0


class AudioCapture:
    def __init__(
        self,
        audio_in: AudioIn | None,
        *,
        on_frame: Callable[[AudioFrame], None] | None = None,
        pre_roll_s: float = 3.0,
        sample_rate: int = 16000,
    ) -> None:
        self.audio_in = audio_in
        self.on_frame = on_frame
        self.sample_rate = sample_rate
        self.ring = RingBuffer(pre_roll_s, sample_rate)
        self._frames = 0
        self._started = False
        self._lock = threading.RLock()
        self._last_error = ""

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> CaptureHealth:
        if self.audio_in is None:
            return CaptureHealth("disabled", "no microphone in HAL")
        status = self.audio_in.start(self._handle_frame)
        if not status.available:
            self._last_error = status.detail
            return CaptureHealth("disabled", status.detail)
        self._started = True
        return CaptureHealth("ok", "capture running")

    def stop(self) -> None:
        if self.audio_in is not None:
            try:
                self.audio_in.stop()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("audio capture stop failed")
        self._started = False

    def health(self) -> CaptureHealth:
        if not self._started:
            return CaptureHealth(
                "disabled",
                self._last_error or "capture stopped",
                self._frames,
                self.ring.duration_ms,
            )
        return CaptureHealth(
            "ok",
            "capture running",
            self._frames,
            self.ring.duration_ms,
        )

    def _handle_frame(self, frame: AudioFrame) -> None:
        if frame.sample_rate != self.sample_rate or frame.channels != 1:
            return
        with self._lock:
            self._frames += 1
            self.ring.append(frame.pcm, frame.duration_ms)
        callback = self.on_frame
        if callback is not None:
            callback(frame)


def probe_audio(audio_in: AudioIn | None) -> DeviceStatus:
    if audio_in is None:
        return DeviceStatus.missing("no microphone in HAL")
    return audio_in.probe()
