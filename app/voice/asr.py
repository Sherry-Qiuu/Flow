"""Cloud/offline ASR adapters with a deterministic test provider."""

from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from voice.config import SpeechSettings


@dataclass(frozen=True)
class AsrResult:
    text: str
    confidence: float = 1.0
    source: str = "unknown"

    @property
    def empty(self) -> bool:
        return not self.text.strip()


class AsrProvider:
    name = "unknown"

    @property
    def available(self) -> bool:
        return False

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        raise NotImplementedError


class NullAsr(AsrProvider):
    name = "null"
    available = True

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        del pcm, sample_rate
        return AsrResult("", 0.0, self.name)


class ScriptedAsr(AsrProvider):
    """Test/demo provider; each recognition pops the next phrase."""

    name = "scripted"
    available = True

    def __init__(self, transcripts: list[str] | None = None) -> None:
        self.transcripts = list(transcripts or [])
        self.calls = 0

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        del pcm, sample_rate
        self.calls += 1
        if not self.transcripts:
            return AsrResult("", 0.0, self.name)
        return AsrResult(self.transcripts.pop(0), 0.95, self.name)


class CloudAsr(AsrProvider):
    """Minimal HTTP JSON adapter; the endpoint owns the vendor protocol."""

    name = "cloud"
    available = True

    def __init__(
        self,
        url: str,
        *,
        api_key: str = "",
        timeout: float = 8.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        body = json.dumps(
            {
                "audio": base64.b64encode(pcm).decode("ascii"),
                "encoding": "pcm_s16le",
                "sample_rate": sample_rate,
                "channels": 1,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.url,
            data=body,
            headers=headers,
            method="POST",
        )
        with self._opener(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = str(payload.get("text", "")).strip()
        confidence = float(payload.get("confidence", 0.9))
        return AsrResult(text, confidence, self.name)


class VoskAsr(AsrProvider):
    name = "vosk"

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        sample_rate: int = 16000,
    ) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.sample_rate = sample_rate
        self._model = None
        self._error = ""

    @property
    def available(self) -> bool:
        if self.model_path is None or not self.model_path.is_dir():
            return False
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False
        return True

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        if not self.available:
            raise RuntimeError("Vosk model or package is unavailable")
        import vosk

        if self._model is None:
            self._model = vosk.Model(str(self.model_path))
        recognizer = vosk.KaldiRecognizer(
            self._model,
            sample_rate or self.sample_rate,
        )
        recognizer.AcceptWaveform(pcm)
        result = json.loads(recognizer.FinalResult())
        return AsrResult(
            str(result.get("text", "")).strip(),
            0.8,
            self.name,
        )


class FallbackAsr(AsrProvider):
    """Try cloud first; switch to offline after a failure and report it."""

    name = "fallback"

    def __init__(
        self,
        primary: AsrProvider | None,
        secondary: AsrProvider | None,
        *,
        on_fallback: Callable[[str], None] | None = None,
        failures_before_fallback: int = 2,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.on_fallback = on_fallback
        self.failures_before_fallback = max(1, failures_before_fallback)
        self._failures = 0
        self._using_secondary = False
        self.last_source = ""

    @property
    def available(self) -> bool:
        return bool(
            (self.primary is not None and self.primary.available)
            or (self.secondary is not None and self.secondary.available)
        )

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16000) -> AsrResult:
        if (
            self.primary is not None
            and self.primary.available
            and not self._using_secondary
        ):
            try:
                result = self.primary.transcribe(
                    pcm,
                    sample_rate=sample_rate,
                )
                self._failures = 0
                self.last_source = result.source
                return result
            except Exception as exc:
                self._failures += 1
                if self._failures >= self.failures_before_fallback:
                    self._using_secondary = True
                    if self.on_fallback is not None:
                        self.on_fallback(str(exc))
        if self.secondary is not None and self.secondary.available:
            result = self.secondary.transcribe(
                pcm,
                sample_rate=sample_rate,
            )
            self.last_source = result.source
            return result
        return AsrResult("", 0.0, "unavailable")


def build_asr(
    settings: SpeechSettings | None = None,
    *,
    env: dict[str, str] | None = None,
) -> AsrProvider:
    del settings
    values = env if env is not None else os.environ
    url = values.get("FLOW_ASR_URL", "").strip()
    key = values.get("FLOW_ASR_KEY", "").strip()
    model = values.get("FLOW_VOSK_MODEL", "").strip()
    cloud = CloudAsr(url, api_key=key) if url else None
    local = VoskAsr(model) if model else None
    if cloud is None and local is None:
        return NullAsr()
    return FallbackAsr(cloud, local)
