"""T07 speech output, cache and emotion tests."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path

from bus.local import LocalEventBus
from hal.contracts import AudioOut, DeviceStatus
from planner.timeutil import tz_for
from voice.say import SayService, SaySettings, is_quiet
from voice.tts import AudioCache, SilentTts, TtsProvider


class FakeAudioOut(AudioOut):
    name = "audio_out"

    def __init__(self) -> None:
        super().__init__()
        self.played: list[str] = []
        self.stops = 0
        self._volume = 0.5

    def probe(self):
        return DeviceStatus.ok("fake")

    def open(self):
        self._opened = True
        return DeviceStatus.ok("fake")

    def close(self):
        self._opened = False

    def health(self):
        return self.probe()

    def play(self, path_or_pcm) -> bool:
        self.played.append(str(path_or_pcm))
        return True

    def stop(self) -> None:
        self.stops += 1

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))

    @property
    def volume(self) -> float:
        return self._volume


class FakeTts(TtsProvider):
    name = "fake"
    available = True

    def __init__(self, path: Path) -> None:
        self.path = path

    def synthesize(self, text: str, voice: str = "") -> Path | None:
        del voice
        self.path.write_bytes(b"RIFF" + b"\0" * 100)
        return self.path


def test_say_events_dedupe_and_quiet(workspace_tmp):
    bus = LocalEventBus()
    said: list[dict] = []
    faces: list[dict] = []
    bus.subscribe("assistant.say", said.append)
    bus.subscribe("emotion.face", faces.append)
    now = datetime(2026, 11, 7, 23, 0, tzinfo=tz_for("Asia/Shanghai"))
    service = SayService(
        audio_out=None,
        publisher=bus,
        settings=SaySettings(
            cache_dir=str(workspace_tmp / f"say-{uuid.uuid4().hex}")
        ),
    )
    service.start()
    try:
        assert service.say("该休息了", "concerned", "reminder", now=now)
        assert not service.say("该休息了", "concerned", "reminder", now=now)
        assert said[-1]["text"] == "该休息了"
        assert said[-1]["quiet"] is True
        assert faces[-1]["emotion"] == "concerned"
    finally:
        service.stop()


def test_tts_cache_and_player(workspace_tmp):
    source = workspace_tmp / f"tts-{uuid.uuid4().hex}.wav"
    output = FakeAudioOut()
    bus = LocalEventBus()
    service = SayService(
        tts=FakeTts(source),
        audio_out=output,
        publisher=bus,
        settings=SaySettings(
            cache_dir=str(workspace_tmp / f"cache-{uuid.uuid4().hex}")
        ),
    )
    service.start()
    try:
        service.say("你好")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not output.played:
            time.sleep(0.01)
        assert output.played
        assert source.exists() is False
    finally:
        service.stop()


def test_silent_tts_and_audio_cache_key(workspace_tmp):
    cache = AudioCache(workspace_tmp / "cache-test", max_files=2)
    assert cache.get("missing") is None
    source = workspace_tmp / f"cache-src-{uuid.uuid4().hex}.wav"
    source.write_bytes(b"RIFF" + b"\0" * 100)
    target = cache.put("hello", source)
    assert target.exists()
    assert cache.get("hello") == target
    source.unlink()


def test_quiet_hours():
    settings = SaySettings()
    assert is_quiet(
        datetime(2026, 11, 7, 23, 0, tzinfo=tz_for("Asia/Shanghai")),
        settings,
    )
    assert not is_quiet(
        datetime(2026, 11, 7, 12, 0, tzinfo=tz_for("Asia/Shanghai")),
        settings,
    )
    assert SilentTts().available is True
