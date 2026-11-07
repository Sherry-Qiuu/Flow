"""T07 TTS providers and local audio cache."""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import wave
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class TtsProvider(ABC):
    name = "tts"

    @property
    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def synthesize(self, text: str, voice: str = "") -> Path | None:
        ...


class SilentTts(TtsProvider):
    """Offline/no-engine fallback: text still reaches the screen."""

    name = "silent"

    @property
    def available(self) -> bool:
        return True

    def synthesize(self, text: str, voice: str = "") -> Path | None:
        del text, voice
        return None


class EspeakTts(TtsProvider):
    """Offline espeak-ng adapter; writes a mono 16 kHz WAV."""

    name = "espeak"

    def __init__(self, binary: str | None = None) -> None:
        self.binary = binary or shutil.which("espeak-ng") or shutil.which(
            "espeak"
        )

    @property
    def available(self) -> bool:
        return self.binary is not None

    def synthesize(self, text: str, voice: str = "") -> Path | None:
        if not self.binary:
            return None
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            target = Path(tmp.name)
        command = [self.binary, "-v", voice or "zh", "-w", str(target), text]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except Exception:
            logger.exception("espeak synthesis failed")
            target.unlink(missing_ok=True)
            return None
        if not target.is_file() or target.stat().st_size <= 44:
            target.unlink(missing_ok=True)
            return None
        return target


class AudioCache:
    def __init__(self, root: str | Path, *, max_files: int = 200) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_files = max(1, int(max_files))

    def key(self, text: str, voice: str = "") -> str:
        return hashlib.sha256(
            f"{voice}\0{text}".encode("utf-8")
        ).hexdigest()[:24]

    def path_for(self, text: str, voice: str = "") -> Path:
        return self.root / f"{self.key(text, voice)}.wav"

    def get(self, text: str, voice: str = "") -> Path | None:
        path = self.path_for(text, voice)
        return path if path.is_file() and path.stat().st_size > 44 else None

    def put(self, text: str, source: Path, voice: str = "") -> Path:
        target = self.path_for(text, voice)
        target.write_bytes(source.read_bytes())
        self._trim()
        return target

    def _trim(self) -> None:
        files = sorted(
            self.root.glob("*.wav"),
            key=lambda path: path.stat().st_mtime,
        )
        for old in files[: -self.max_files]:
            old.unlink(missing_ok=True)


def inspect_wav(path: Path) -> tuple[int, int, int] | None:
    try:
        with wave.open(str(path), "rb") as wav:
            return wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
    except (wave.Error, OSError):
        return None


class EdgeTts(TtsProvider):
    """Optional edge-tts hook; requires network and ffmpeg.

    The class is intentionally thin: the deterministic offline path is
    espeak, and edge-tts is only used when the package/ffmpeg exist.
    """

    name = "edge"

    def __init__(self) -> None:
        self._module = None
        try:
            import edge_tts

            self._module = edge_tts
        except ImportError:
            self._module = None

    @property
    def available(self) -> bool:
        return self._module is not None and shutil.which("ffmpeg") is not None

    def synthesize(self, text: str, voice: str = "") -> Path | None:
        # Synchronous wrapper is intentionally not used in the default
        # path; edge-tts needs an async loop and ffmpeg conversion.
        del text, voice
        return None
