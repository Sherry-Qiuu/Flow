"""Mock microphone generating a soft 16 kHz tone stream."""

from __future__ import annotations

import logging
import math
import threading
import time
from array import array
from collections.abc import Callable

from hal.contracts import AudioFrame, DeviceStatus, EventPublisher
from hal.mock.base import MockDevice

logger = logging.getLogger(__name__)


class MockAudioIn(MockDevice):
    """Emit evenly paced mono 16-bit PCM frames.

    A low-volume 440 Hz tone is enough to exercise VAD, buffering and
    resampling code without audio hardware. Tests can shorten the frame
    interval and stop the stream deterministically.
    """

    name = "audio_in"

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        tone_hz: float = 440.0,
        amplitude: float = 0.06,
    ) -> None:
        super().__init__(publisher, detail="mock microphone")
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.tone_hz = tone_hz
        self.amplitude = max(0.0, min(1.0, amplitude))
        self.frame_samples = max(1, sample_rate * frame_ms // 1000)
        self._callback: Callable[[AudioFrame], None] | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._phase = 0.0
        self._frames_emitted = 0
        self._last_frame: AudioFrame | None = None

    @property
    def frames_emitted(self) -> int:
        return self._frames_emitted

    @property
    def last_frame(self) -> AudioFrame | None:
        return self._last_frame

    def start(self, on_frame: Callable[[AudioFrame], None]) -> DeviceStatus:
        if not callable(on_frame):
            raise TypeError("on_frame must be callable")
        with self._lock:
            if not self._opened:
                status = self.open()
                if not status.available:
                    return status
            if self._thread is not None and self._thread.is_alive():
                return DeviceStatus.ok("mock microphone already running")
            self._callback = on_frame
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="flow-mock-audio-in",
                daemon=True,
            )
            self._thread.start()
        return DeviceStatus.ok("mock microphone streaming")

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._callback = None

    def close(self) -> None:
        self.stop()
        super().close()

    def _run(self) -> None:
        interval = self.frame_samples / float(self.sample_rate)
        next_at = time.monotonic() + interval
        while not self._stop.is_set():
            delay = next_at - time.monotonic()
            if delay > 0 and self._stop.wait(delay):
                break
            next_at += interval
            if next_at < time.monotonic() - interval:
                next_at = time.monotonic() + interval
            if not self.probe().available:
                break
            frame = self._make_frame()
            callback = self._callback
            if callback is None:
                break
            try:
                callback(frame)
            except Exception:  # pragma: no cover - upper layer boundary
                logger.exception("mock audio frame handler failed")

    def _make_frame(self) -> AudioFrame:
        samples = array("h")
        step = 2.0 * math.pi * self.tone_hz / self.sample_rate
        peak = int(32767 * self.amplitude)
        phase = self._phase
        for _ in range(self.frame_samples):
            # A slow amplitude envelope sounds less like a test beep.
            envelope = 0.6 + 0.4 * math.sin(phase / 37.0)
            samples.append(int(peak * envelope * math.sin(phase)))
            phase += step
            if phase > 2.0 * math.pi:
                phase -= 2.0 * math.pi
        self._phase = phase
        frame = AudioFrame(
            pcm=samples.tobytes(),
            sample_rate=self.sample_rate,
            channels=1,
        )
        self._frames_emitted += 1
        self._last_frame = frame
        return frame

    def health(self) -> DeviceStatus:
        return self.probe()
