"""Energy VAD with 300 ms endpointing and partial callbacks."""

from __future__ import annotations

import math
from array import array
from dataclasses import dataclass

from voice.config import SpeechSettings


@dataclass(frozen=True)
class VadEvent:
    kind: str
    pcm: bytes = b""
    duration_ms: float = 0.0
    reason: str = ""


class EnergyVad:
    """Dependency-free VAD; good enough for near-field MVP audio."""

    def __init__(self, settings: SpeechSettings | None = None) -> None:
        self.settings = settings or SpeechSettings()
        self._speaking = False
        self._voiced_ms = 0.0
        self._silence_ms = 0.0
        self._utterance_ms = 0.0
        self._partial_ms = 0.0
        self._audio: list[bytes] = []
        self._start_frames = 0

    @property
    def speaking(self) -> bool:
        return self._speaking

    def push(
        self,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
        duration_ms: float | None = None,
    ) -> list[VadEvent]:
        if not pcm:
            return []
        duration = (
            duration_ms
            if duration_ms is not None
            else len(pcm) * 1000.0 / (sample_rate * 2)
        )
        energy = rms(pcm)
        voiced = energy >= self.settings.vad_threshold
        events: list[VadEvent] = []

        if not self._speaking:
            if voiced:
                self._start_frames += 1
                self._voiced_ms += duration
                if (
                    self._start_frames >= 2
                    and self._voiced_ms >= self.settings.min_speech_ms
                ):
                    self._speaking = True
                    self._silence_ms = 0.0
                    self._utterance_ms = 0.0
                    self._partial_ms = 0.0
                    self._audio = []
                    events.append(
                        VadEvent("speech_start", reason="energy")
                    )
            else:
                self._start_frames = 0
                self._voiced_ms = 0.0
            if not self._speaking:
                return events

        self._audio.append(pcm)
        self._utterance_ms += duration
        if voiced:
            self._silence_ms = 0.0
        else:
            self._silence_ms += duration

        self._partial_ms += duration
        if (
            self._partial_ms >= self.settings.partial_interval_ms
            and self._silence_ms < 100
        ):
            self._partial_ms = 0.0
            events.append(
                VadEvent(
                    "partial",
                    b"".join(self._audio),
                    self._utterance_ms,
                )
            )

        if self._silence_ms >= self.settings.silence_ms:
            events.append(self._end("silence"))
        elif self._utterance_ms >= self.settings.max_utterance_s * 1000:
            events.append(self._end("max_duration"))
        return events

    def flush(self) -> VadEvent | None:
        if not self._speaking:
            return None
        return self._end("flush")

    def reset(self) -> None:
        self._speaking = False
        self._start_frames = 0
        self._voiced_ms = 0.0
        self._silence_ms = 0.0
        self._utterance_ms = 0.0
        self._partial_ms = 0.0
        self._audio = []

    def _end(self, reason: str) -> VadEvent:
        pcm = b"".join(self._audio)
        duration = self._utterance_ms
        self.reset()
        return VadEvent("speech_end", pcm, duration, reason)


def rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    total = sum(float(sample) * float(sample) for sample in samples)
    return math.sqrt(total / len(samples)) / 32768.0
