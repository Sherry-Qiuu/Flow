"""T06 speech pipeline settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechSettings:
    enabled: bool = True
    sample_rate: int = 16000
    pre_roll_s: float = 3.0
    silence_ms: int = 300
    vad_threshold: float = 0.018
    min_speech_ms: int = 120
    partial_interval_ms: int = 700
    max_utterance_s: int = 30
    empty_prompt_after: int = 3
    barge_in: bool = True
    barge_in_threshold: float = 0.03
    debug_audio: bool = False

    def __post_init__(self) -> None:
        if self.sample_rate != 16000:
            raise ValueError("T06 requires 16 kHz mono audio")
        if self.pre_roll_s < 0 or self.pre_roll_s > 5:
            raise ValueError("pre_roll_s must be in [0, 5]")
        if self.silence_ms < 100:
            raise ValueError("silence_ms must be at least 100")
        if self.max_utterance_s < 1:
            raise ValueError("max_utterance_s must be positive")
        if self.empty_prompt_after < 1:
            raise ValueError("empty_prompt_after must be positive")
