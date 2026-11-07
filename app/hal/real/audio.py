"""Microphone and speaker implementations backed by sounddevice."""

from __future__ import annotations

import logging
import threading
import wave
from array import array
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hal.contracts import (
    AudioFrame,
    AudioIn,
    AudioOut,
    DeviceStatus,
)

logger = logging.getLogger(__name__)


def _resample_pcm16(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    """Linearly resample mono 16-bit PCM without third-party packages."""
    if source_rate == target_rate or not pcm:
        return pcm
    samples = array("h")
    samples.frombytes(pcm)
    if not samples:
        return b""
    out_length = max(1, int(round(len(samples) * target_rate / source_rate)))
    ratio = source_rate / float(target_rate)
    out = array("h")
    last = len(samples) - 1
    for index in range(out_length):
        position = index * ratio
        left = int(position)
        if left >= last:
            out.append(samples[last])
            continue
        fraction = position - left
        value = samples[left] * (1.0 - fraction) + samples[left + 1] * fraction
        out.append(max(-32768, min(32767, int(value))))
    return out.tobytes()


def _apply_gain(pcm: bytes, volume: float) -> bytes:
    gain = max(0.0, min(1.0, float(volume)))
    if gain >= 0.999:
        return pcm
    samples = array("h")
    samples.frombytes(pcm)
    for index, sample in enumerate(samples):
        samples[index] = max(-32768, min(32767, int(sample * gain)))
    return samples.tobytes()


class RealAudioIn(AudioIn):
    """Callback microphone normalized to 16 kHz mono."""

    name = "audio_in"

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._stream: Any = None
        self._callback: Callable[[AudioFrame], None] | None = None
        self._capture_rate = 16000
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        return self._opened

    def probe(self) -> DeviceStatus:
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            name = str(device.get("name", "input device"))
            return DeviceStatus.ok(f"input device: {name}")
        except Exception as exc:
            return DeviceStatus.missing(f"no usable microphone: {exc}")

    def open(self) -> DeviceStatus:
        status = self.probe()
        if not status.available:
            return status
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            default_rate = int(device.get("default_samplerate", 16000))
            self._capture_rate = self._pick_rate(sd, default_rate)
            self._opened = True
            return DeviceStatus.ok(
                f"microphone opened at {self._capture_rate} Hz"
            )
        except Exception as exc:
            self._opened = False
            return DeviceStatus.error(f"microphone open failed: {exc}")

    @staticmethod
    def _pick_rate(sd: Any, default_rate: int) -> int:
        for candidate in (16000, default_rate, 48000, 44100):
            if candidate <= 0:
                continue
            try:
                sd.check_input_settings(
                    samplerate=candidate,
                    channels=1,
                    dtype="int16",
                )
                return candidate
            except Exception:
                continue
        raise RuntimeError("microphone does not support mono int16 input")

    def start(self, on_frame: Callable[[AudioFrame], None]) -> DeviceStatus:
        if not callable(on_frame):
            raise TypeError("on_frame must be callable")
        with self._lock:
            if self._running:
                return DeviceStatus.ok("microphone already running")
            if not self._opened:
                status = self.open()
                if not status.available:
                    return status
            try:
                import sounddevice as sd

                blocksize = max(1, int(self._capture_rate * 0.02))
                self._callback = on_frame
                self._stream = sd.RawInputStream(
                    samplerate=self._capture_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=blocksize,
                    callback=self._on_audio,
                )
                self._stream.start()
                self._running = True
            except Exception as exc:
                self._stream = None
                self._callback = None
                self._running = False
                return DeviceStatus.error(f"microphone start failed: {exc}")
        return DeviceStatus.ok(
            f"microphone streaming at {self._capture_rate} Hz"
        )

    def _on_audio(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frames, time_info
        if status:
            logger.warning("microphone stream status: %s", status)
        pcm = bytes(indata)
        if self._capture_rate != 16000:
            pcm = _resample_pcm16(pcm, self._capture_rate, 16000)
        frame = AudioFrame(pcm=pcm, sample_rate=16000, channels=1)
        callback = self._callback
        if callback is not None:
            try:
                callback(frame)
            except Exception:  # pragma: no cover - upper layer boundary
                logger.exception("microphone frame handler failed")

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._running = False
            self._callback = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:  # pragma: no cover - hardware boundary
                logger.exception("failed to stop microphone stream")

    def close(self) -> None:
        self.stop()
        self._opened = False

    def health(self) -> DeviceStatus:
        if self._opened and self._running:
            return DeviceStatus.ok("microphone streaming")
        return self.probe()


class RealAudioOut(AudioOut):
    """Speaker playing raw PCM and 16-bit WAV files."""

    name = "audio_out"

    def __init__(self, volume: float = 0.7) -> None:
        super().__init__()
        self._volume = max(0.0, min(1.0, volume))

    @property
    def is_open(self) -> bool:
        return self._opened

    @property
    def volume(self) -> float:
        return self._volume

    def probe(self) -> DeviceStatus:
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="output")
            name = str(device.get("name", "output device"))
            return DeviceStatus.ok(f"output device: {name}")
        except Exception as exc:
            return DeviceStatus.missing(f"no usable speaker: {exc}")

    def open(self) -> DeviceStatus:
        status = self.probe()
        self._opened = status.available
        return status

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, float(value)))

    def play(self, path_or_pcm: str | Path | bytes) -> bool:
        if not self._opened:
            status = self.open()
            if not status.available:
                return False
        try:
            if isinstance(path_or_pcm, (bytes, bytearray)):
                pcm = bytes(path_or_pcm)
                if not pcm:
                    return False
                self._play_pcm(pcm, 16000, 1)
                return True
            path = Path(path_or_pcm)
            if not path.is_file():
                return False
            with wave.open(str(path), "rb") as wav:
                if wav.getsampwidth() != 2:
                    logger.warning("only 16-bit WAV files are supported")
                    return False
                pcm = wav.readframes(wav.getnframes())
                self._play_pcm(pcm, wav.getframerate(), wav.getnchannels())
            return True
        except Exception as exc:
            logger.warning("speaker playback failed, degrading: %s", exc)
            return False

    def _play_pcm(self, pcm: bytes, rate: int, channels: int) -> None:
        import sounddevice as sd

        pcm = _apply_gain(pcm, self._volume)
        with sd.RawOutputStream(
            samplerate=rate,
            channels=channels,
            dtype="int16",
        ) as stream:
            stream.write(pcm)
