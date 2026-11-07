"""SpeechPipeline: capture -> VAD -> ASR -> speech.partial/final."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from bus import topics
from hal.contracts import AudioFrame, AudioIn, AudioOut
from voice.asr import AsrProvider, AsrResult, NullAsr
from voice.bargein import EmptyRecognitionGuard, EnergyBargeIn
from voice.capture import AudioCapture, CaptureHealth
from voice.config import SpeechSettings
from voice.vad import EnergyVad, VadEvent

logger = logging.getLogger(__name__)


class SpeechHealth:
    def __init__(
        self,
        state: str,
        detail: str = "",
        *,
        finals: int = 0,
        partials: int = 0,
    ) -> None:
        self.state = state
        self.detail = detail
        self.finals = finals
        self.partials = partials

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "detail": self.detail,
            "finals": self.finals,
            "partials": self.partials,
        }


class SpeechPipeline:
    def __init__(
        self,
        audio_in: AudioIn | None,
        asr: AsrProvider,
        *,
        publisher: Any = None,
        audio_out: AudioOut | None = None,
        settings: SpeechSettings | None = None,
        capture: AudioCapture | None = None,
        vad: EnergyVad | None = None,
    ) -> None:
        self.settings = settings or SpeechSettings()
        self.asr = asr
        self.publisher = publisher
        self.audio_out = audio_out
        self.capture = capture or AudioCapture(
            audio_in,
            on_frame=self._on_frame,
            pre_roll_s=self.settings.pre_roll_s,
            sample_rate=self.settings.sample_rate,
        )
        self.vad = vad or EnergyVad(self.settings)
        self.barge = EnergyBargeIn(
            threshold=self.settings.barge_in_threshold
        )
        self.guard = EmptyRecognitionGuard(
            limit=self.settings.empty_prompt_after
        )
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="flow-asr",
        )
        self._started = False
        self._stopped = False
        self._tts_active = False
        self._pre_roll = b""
        self._last_text = ""
        self._last_error = ""
        self._finals = 0
        self._partials = 0
        self._lock = threading.RLock()

    def start(self) -> SpeechHealth:
        if not self.settings.enabled:
            return SpeechHealth("disabled", "speech disabled by config")
        if isinstance(self.asr, NullAsr) or not self.asr.available:
            return SpeechHealth(
                "disabled",
                "no ASR configured (FLOW_ASR_URL or FLOW_VOSK_MODEL)",
            )
        health = self.capture.start()
        if not health.healthy:
            return SpeechHealth("disabled", health.detail)
        self._started = True
        self._stopped = False
        return SpeechHealth("ok", "speech pipeline listening")

    def stop(self) -> None:
        self._stopped = True
        self._started = False
        self.capture.stop()
        self._executor.shutdown(wait=False)

    def health(self) -> SpeechHealth:
        if not self._started:
            return SpeechHealth(
                "disabled",
                self._last_error or "speech pipeline stopped",
                finals=self._finals,
                partials=self._partials,
            )
        capture = self.capture.health()
        if not capture.healthy:
            return SpeechHealth(
                "degraded",
                capture.detail,
                finals=self._finals,
                partials=self._partials,
            )
        return SpeechHealth(
            "ok",
            "speech pipeline listening",
            finals=self._finals,
            partials=self._partials,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "enabled": self.settings.enabled,
            "started": self._started,
            "tts_active": self._tts_active,
            "finals": self._finals,
            "partials": self._partials,
            "last_text": self._last_text,
            "capture": self.capture.health().to_dict(),
        }

    def speak(self, pcm: bytes) -> bool:
        if self.audio_out is None or not pcm:
            return False
        self._tts_active = True
        self.barge.reset()
        try:
            return self.audio_out.play(pcm)
        except Exception:
            logger.exception("TTS playback failed")
            return False
        finally:
            self._tts_active = False

    def _on_frame(self, frame: AudioFrame) -> None:
        if not self._started or self._stopped:
            return
        if self._tts_active:
            if self.settings.barge_in and self.barge.feed(frame.pcm):
                self._interrupt()
            return
        for event in self.vad.push(
            frame.pcm,
            sample_rate=frame.sample_rate,
            duration_ms=frame.duration_ms,
        ):
            self._handle_vad(event)

    def _handle_vad(self, event: VadEvent) -> None:
        if event.kind == "speech_start":
            self._pre_roll = self.capture.ring.pre_roll(
                self.settings.pre_roll_s
            )
            self._publish(topics.SPEECH_STARTED, {})
        elif event.kind == "partial":
            self._submit(self._pre_roll + event.pcm, final=False)
        elif event.kind == "speech_end":
            audio = self._pre_roll + event.pcm
            self._pre_roll = b""
            self._submit(audio, final=True)

    def _submit(self, pcm: bytes, *, final: bool) -> None:
        if not pcm:
            return
        try:
            self._executor.submit(self._recognize, pcm, final)
        except RuntimeError:
            return

    def _recognize(self, pcm: bytes, final: bool) -> None:
        try:
            result = self.asr.transcribe(
                pcm,
                sample_rate=self.settings.sample_rate,
            )
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("ASR failed")
            return
        if not final:
            self._partials += 1
            if result.text.strip():
                self._publish(
                    topics.SPEECH_PARTIAL,
                    self._payload(result),
                )
            return
        self._finals += 1
        prompt = self.guard.record(result.text)
        if prompt is not None:
            self._publish(topics.SPEECH_EMPTY, {"text": prompt})
        if result.text.strip():
            self._last_text = result.text.strip()
            self._publish(
                topics.SPEECH_FINAL,
                self._payload(result),
            )

    def _interrupt(self) -> None:
        self._tts_active = False
        self.barge.reset()
        if self.audio_out is not None:
            try:
                self.audio_out.stop()
            except Exception:
                logger.exception("audio_out.stop failed")
        self._publish(
            topics.SPEECH_BARGE_IN,
            {"reason": "user_speech"},
        )

    def _payload(self, result: AsrResult) -> dict[str, Any]:
        return {
            "text": result.text.strip(),
            "confidence": result.confidence,
            "source": result.source,
        }

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("speech publish failed: %s", topic)
