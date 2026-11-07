"""HAL contract and mock-device tests."""

from __future__ import annotations

import threading
import time

import pytest

from bus import topics
from bus.local import LocalEventBus
from hal.contracts import AudioFrame, DeviceState, PhoneState
from hal.factory import create_hal


@pytest.fixture
def hal():
    instance = create_hal("mock")
    yield instance
    instance.close()


def test_mock_backend_opens_every_device(hal):
    statuses = hal.open_all()
    assert hal.backend == "mock"
    assert set(statuses) == {
        "display",
        "camera",
        "audio_in",
        "audio_out",
        "phone_stand",
        "gesture",
    }
    assert all(status.available for status in statuses.values())


def test_camera_capture_returns_jpeg(hal):
    assert hal.camera.open().available
    data = hal.camera.capture()
    assert data is not None
    assert data.startswith(b"\xff\xd8")
    assert data.endswith(b"\xff\xd9")
    assert len(data) > 1000


def test_unplugged_camera_degrades_without_crashing(hal):
    assert hal.camera.open().available
    assert hal.camera.capture() is not None
    hal.camera.unplug()
    assert hal.camera.capture() is None
    status = hal.camera.health()
    assert status.state is DeviceState.MISSING
    assert "unplugged" in status.detail
    # Other devices keep working.
    assert hal.display.open().available


def test_audio_in_streams_16khz_mono_frames(hal):
    assert hal.audio_in.open().available
    frames: list[AudioFrame] = []
    received = threading.Event()

    def on_frame(frame: AudioFrame) -> None:
        frames.append(frame)
        if len(frames) >= 5:
            received.set()

    status = hal.audio_in.start(on_frame)
    assert status.available
    assert received.wait(1.5)
    hal.audio_in.stop()
    assert frames
    assert all(frame.sample_rate == 16000 for frame in frames)
    assert all(frame.channels == 1 for frame in frames)
    assert all(len(frame.pcm) > 0 for frame in frames)


def test_audio_out_volume_and_playback(hal):
    assert hal.audio_out.open().available
    pcm = b"\x00\x00" * 1600
    assert hal.audio_out.play(pcm)
    hal.audio_out.set_volume(1.5)
    assert hal.audio_out.volume == 1.0
    hal.audio_out.set_volume(-0.2)
    assert hal.audio_out.volume == 0.0
    assert not hal.audio_out.play(b"")
    assert hal.audio_out.plays


def test_phone_changed_event_within_300ms():
    bus = LocalEventBus()
    hal = create_hal("mock", publisher=bus)
    events: list[dict] = []
    event = threading.Event()

    def on_phone(payload: dict) -> None:
        events.append(payload)
        event.set()

    unsubscribe = bus.subscribe(topics.PHONE_CHANGED, on_phone)
    try:
        assert hal.phone_stand.open().available
        started = time.perf_counter()
        hal.phone_stand.place_phone(charging=True)
        assert event.wait(0.3), "phone.changed did not arrive within 300 ms"
        elapsed = time.perf_counter() - started
        assert elapsed < 0.3
        assert events[-1]["present"] is True
        assert events[-1]["charging"] is True
        assert times_current(events[-1]) > 0

        # Repeating the same snapshot must not spam the bus.
        event.clear()
        hal.phone_stand.place_phone(charging=True)
        assert not event.wait(0.25)
        assert len(events) == 1
    finally:
        unsubscribe()
        hal.close()


def test_phone_state_defaults_to_safe_snapshot(hal):
    state = hal.phone_stand.state()
    assert isinstance(state, PhoneState)
    assert state["present"] is False
    assert dict(state) == {
        "present": False,
        "charging": False,
        "current_ma": 0,
        "distance_mm": 120,
    }
    assert state.to_dict() == {
        "present": False,
        "charging": False,
        "current_ma": 0,
        "distance_mm": 120,
    }


def test_gesture_events(hal):
    received: list[str] = []
    assert hal.gesture.start(received.append).available
    hal.gesture.trigger("wave")
    hal.gesture.stop()
    assert received == ["wave"]


def times_current(payload: dict) -> int:
    return int(payload.get("current_ma", 0))
