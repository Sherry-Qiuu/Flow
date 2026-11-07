"""T09 service integration with the local event bus."""

from __future__ import annotations

from bus import topics
from bus.local import LocalEventBus
from gesture.config import GestureSettings
from gesture.service import GestureService
from hal.mock import MockGesture, MockPhoneStand


def make_service() -> tuple[
    GestureService,
    LocalEventBus,
    MockGesture,
    list[dict],
]:
    bus = LocalEventBus()
    gesture = MockGesture(bus)
    phone = MockPhoneStand(bus)
    events: list[dict] = []
    bus.subscribe(topics.GESTURE_DETECTED, events.append)
    service = GestureService(
        GestureSettings(),
        bus,
        gesture,
        phone,
    )
    return service, bus, gesture, events


def test_service_publishes_gesture_detected():
    service, _, gesture, events = make_service()
    health = service.start()
    assert health.state == "ok"
    gesture.open()
    gesture.trigger("wave")
    assert events
    assert events[0]["type"] == "wave"
    assert events[0]["action"] == "confirm"
    service.stop()


def test_service_maps_phone_events_to_place_and_take():
    service, bus, _, events = make_service()
    service.start()
    bus.publish(topics.PHONE_CHANGED, {"present": True})
    bus.publish(topics.PHONE_CHANGED, {"present": False})
    kinds = [event["type"] for event in events]
    assert "phone_place" in kinds
    assert "phone_take" in kinds
    service.stop()


def test_service_accepts_distance_observations():
    service, _, _, events = make_service()
    service.start()
    service.observe_distance(50)
    assert events[-1]["type"] == "approach"
    service.observe_distance(400)
    service.stop()


def test_missing_sensor_degrades_to_disabled():
    bus = LocalEventBus()
    gesture = MockGesture(bus)
    gesture.set_available(False)
    service = GestureService(
        GestureSettings(),
        bus,
        gesture,
        MockPhoneStand(bus),
    )
    health = service.start()
    assert health.state == "disabled"
    assert "unavailable" in health.detail
    assert service.health().healthy


def test_stop_unsubscribes_and_stops_sensor():
    service, bus, gesture, events = make_service()
    service.start()
    service.stop()
    bus.publish(topics.PHONE_CHANGED, {"present": True})
    gesture.trigger("wave")
    assert events == []


def test_snapshot_reports_presence_and_event_count():
    service, _, gesture, _ = make_service()
    service.start()
    gesture.open()
    gesture.trigger("wave")
    snapshot = service.snapshot()
    assert snapshot["events"] == 1
    assert snapshot["last_event"]["type"] == "wave"
    assert "presence" in snapshot
    service.stop()
