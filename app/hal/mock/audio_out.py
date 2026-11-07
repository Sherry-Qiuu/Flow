"""Mock speaker that records playback instead of using ALSA."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hal.contracts import DeviceStatus, EventPublisher
from hal.mock.base import MockDevice


class MockAudioOut(MockDevice):
    name = "audio_out"

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        *,
        volume: float = 0.7,
    ) -> None:
        super().__init__(publisher, detail="mock speaker")
        self._volume = max(0.0, min(1.0, volume))
        self._plays: list[dict[str, Any]] = []
        self._stops = 0

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def plays(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._plays)

    @property
    def stops(self) -> int:
        return self._stops

    def stop(self) -> None:
        self._stops += 1

    def play(self, path_or_pcm: str | Path | bytes) -> bool:
        if not self._opened:
            status = self.open()
            if not status.available:
                return False
        if isinstance(path_or_pcm, (bytes, bytearray)):
            pcm = bytes(path_or_pcm)
            if not pcm:
                return False
            duration_ms = len(pcm) * 1000.0 / (16000 * 2)
            entry = {
                "kind": "pcm",
                "bytes": len(pcm),
                "duration_ms": round(duration_ms, 3),
            }
        else:
            path = Path(path_or_pcm)
            if not path.is_file():
                return False
            entry = {
                "kind": "file",
                "path": str(path),
                "bytes": path.stat().st_size,
            }
        entry["volume"] = self._volume
        self._plays.append(entry)
        return True

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, float(value)))

    def clear_history(self) -> None:
        self._plays.clear()

    def health(self) -> DeviceStatus:
        return self.probe()
