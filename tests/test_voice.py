"""T06 capture, VAD, ASR fallback, barge-in and pipeline tests."""

from __future__ import annotations

import threading
import time
from array import array

from bus.local import LocalEventBus
from channel.builtin import build_registry
from channel.base import ChannelContext
from channel.machine import ChannelMachine
from channel.service import ChannelService
from hal.contracts import (
    AudioFrame,
    AudioIn,
    AudioOut,
    DeviceStatus,
)
from voice.asr import (
    AsrResult,
    CloudAsr,
    FallbackAsr,
    ScriptedAsr,
    VoskAsr,
    build_asr,
)
from voice.bargein import EmptyRecognitionGuard, EnergyBargeIn
from voice.capture import AudioCapture, RingBuffer
from voice.config import SpeechSettings
from voice.pipeline import SpeechPipeline
from voice.vad import EnergyVad, rms


def pcm_frame(amplitude: int = 3000, samples: int = 320) -> bytes:
    return array("h", [amplitude] * samples).tobytes()


SILENCE = pcm_frame(0)
LOUD = pcm_frame(3000)


class FakeAudioIn(AudioIn):
    name = "audio_in"

    def __init__(self) -> None:
        super().__init__()
        self.callback = None
        self.started = 0

    @property
    def is_open(self) -> bool:
        return self._opened

    def probe(self) -> DeviceStatus:
        return DeviceStatus.ok("fake microphone")

    def open(self) -> DeviceStatus:
        self._opened = True
        return DeviceStatus.ok("fake microphone")

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def start(self, on_frame) -> DeviceStatus:
        self._opened = True
        self.started += 1
        self.callback = on_frame
        return DeviceStatus.ok("fake streaming")

    def stop(self) -> None:
        self.callback = None

    def emit(self, pcm: bytes) -> None:
        if self.callback is not None:
            self.callback(AudioFrame(pcm=pcm))


class FakeAudioOut(AudioOut):
    name = "audio_out"

    def __init__(self) -> None:
        super().__init__()
        self._volume = 0.5
        self.stops = 0
        self.played: list[bytes] = []

    def probe(self) -> DeviceStatus:
        return DeviceStatus.ok("fake speaker")

    def open(self) -> DeviceStatus:
        self._opened = True
        return DeviceStatus.ok("fake speaker")

    def close(self) -> None:
        self._opened = False

    def health(self) -> DeviceStatus:
        return self.probe()

    def play(self, path_or_pcm) -> bool:
        self.played.append(bytes(path_or_pcm))
        return True

    def stop(self) -> None:
        self.stops += 1

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))

    @property
    def volume(self) -> float:
        return self._volume


def test_rms_and_ring_buffer_keep_three_seconds():
    assert rms(SILENCE) == 0
    assert rms(LOUD) > 0.05
    ring = RingBuffer(seconds=0.1)
    for _ in range(20):
        ring.append(LOUD, 20)
    assert ring.duration_ms <= 100.01
    assert ring.pre_roll(0.05)


def test_capture_pre_roll_and_frame_count():
    audio = FakeAudioIn()
    capture = AudioCapture(audio, pre_roll_s=0.1)
    assert capture.start().state == "ok"
    for _ in range(10):
        audio.emit(LOUD)
    assert capture.health().frames == 10
    assert capture.ring.duration_ms <= 100.01
    capture.stop()
    assert audio.callback is None


def test_energy_vad_speech_end_after_silence():
    settings = SpeechSettings(
        silence_ms=100,
        min_speech_ms=40,
        partial_interval_ms=1000,
    )
    vad = EnergyVad(settings)
    events = []
    for _ in range(5):
        events.extend(vad.push(LOUD))
    assert any(event.kind == "speech_start" for event in events)
    assert vad.speaking
    for _ in range(6):
        events.extend(vad.push(SILENCE))
    ends = [event for event in events if event.kind == "speech_end"]
    assert len(ends) == 1
    assert ends[0].reason == "silence"
    assert not vad.speaking


def test_energy_vad_emits_partial():
    settings = SpeechSettings(
        silence_ms=100,
        min_speech_ms=40,
        partial_interval_ms=40,
    )
    vad = EnergyVad(settings)
    events = []
    for _ in range(6):
        events.extend(vad.push(LOUD))
    assert any(event.kind == "partial" for event in events)


def test_pipeline_emits_speech_final():
    audio = FakeAudioIn()
    bus = LocalEventBus()
    finals = []
    bus.subscribe("speech.final", finals.append)
    pipeline = SpeechPipeline(
        audio,
        ScriptedAsr(["打开任务清单"]),
        publisher=bus,
        settings=SpeechSettings(
            silence_ms=100,
            min_speech_ms=40,
            partial_interval_ms=1000,
        ),
    )
    assert pipeline.start().state == "ok"
    for _ in range(5):
        audio.emit(LOUD)
    for _ in range(6):
        audio.emit(SILENCE)
    deadline = threading.Event()
    for _ in range(50):
        if finals:
            break
        deadline.wait(0.02)
    assert finals
    assert finals[0]["text"] == "打开任务清单"
    assert finals[0]["source"] == "scripted"
    assert pipeline.health().state == "ok"
    pipeline.stop()
    audio.emit(LOUD)


def test_pipeline_disabled_without_asr():
    pipeline = SpeechPipeline(FakeAudioIn(), build_asr(env={}))
    assert pipeline.start().state == "disabled"
    assert pipeline.health().healthy


def test_final_text_reaches_channel_service():
    bus = LocalEventBus()
    machine = ChannelMachine(
        build_registry(),
        ChannelContext(),
        publisher=bus,
    )
    channels = ChannelService(machine, publisher=bus, subscriber=bus)
    audio = FakeAudioIn()
    pipeline = SpeechPipeline(
        audio,
        ScriptedAsr(["打开任务清单"]),
        publisher=bus,
        settings=SpeechSettings(
            silence_ms=100,
            min_speech_ms=40,
            partial_interval_ms=1000,
        ),
    )
    try:
        assert channels.start().state == "ok"
        assert pipeline.start().state == "ok"
        for _ in range(5):
            audio.emit(LOUD)
        for _ in range(6):
            audio.emit(SILENCE)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and machine.current_key is None:
            time.sleep(0.02)
        assert machine.current_key == "tasks"
    finally:
        pipeline.stop()
        channels.stop()


def test_cloud_asr_adapter_and_fallback():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"text":"cloud text","confidence":0.88}'

    def opener(request, timeout):
        assert request.method == "POST"
        return Response()

    cloud = CloudAsr("https://asr.invalid", opener=opener)
    result = cloud.transcribe(LOUD)
    assert result.text == "cloud text"
    assert result.source == "cloud"

    class Broken:
        name = "broken"
        available = True

        def transcribe(self, pcm, sample_rate=16000):
            raise RuntimeError("offline")

    fallback = FallbackAsr(
        Broken(),
        ScriptedAsr(["offline text"]),
        failures_before_fallback=1,
    )
    assert fallback.transcribe(LOUD).text == "offline text"
    assert fallback.last_source == "scripted"


def test_barge_in_and_empty_guard():
    barge = EnergyBargeIn(threshold=0.03, min_frames=2)
    assert barge.feed(LOUD) is False
    assert barge.feed(LOUD) is True
    assert barge.feed(SILENCE) is False
    guard = EmptyRecognitionGuard(limit=2, prompt="没听清")
    assert guard.record("") is None
    assert guard.record("") == "没听清"
    assert guard.record("你好") is None


def test_pipeline_speak_and_interrupt():
    audio = FakeAudioIn()
    speaker = FakeAudioOut()
    pipeline = SpeechPipeline(
        audio,
        ScriptedAsr(),
        audio_out=speaker,
    )
    assert pipeline.start().state == "ok"
    assert pipeline.speak(b"hello") is True
    assert speaker.played == [b"hello"]
    pipeline._tts_active = True
    pipeline._interrupt()
    assert speaker.stops == 1
    pipeline.stop()


def test_vosk_unavailable_without_model():
    assert VoskAsr("/missing/model").available is False
    result = FallbackAsr(None, VoskAsr("/missing/model")).transcribe(LOUD)
    assert result.empty
