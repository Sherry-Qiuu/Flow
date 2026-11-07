"""T09 gesture detector and presence state-machine tests."""

from __future__ import annotations

import pytest

from gesture.detector import (
    ACTION_MAP,
    GestureDetector,
    normalize_gesture,
    vote_distribution,
)
from gesture.presence import PresenceDetector


@pytest.mark.parametrize(
    ("raw", "action"),
    list(ACTION_MAP.items()),
)
def test_nine_gestures_map_to_actions(raw, action):
    detector = GestureDetector(window=5, min_votes=2, cooldown_s=1.5)
    event = detector.push_burst(raw, now=10.0)
    assert event is not None
    assert event.type == raw
    assert event.action == action
    assert 0.3 <= event.confidence <= 1.0


def test_debounce_window_requires_enough_votes():
    detector = GestureDetector(window=5, min_votes=3, cooldown_s=0)
    assert detector.push("wave", now=1.0) is None
    assert detector.push("wave", now=1.1) is None
    event = detector.push("wave", now=1.2)
    assert event is not None
    assert event.action == "confirm"


def test_same_action_is_cooled_down():
    detector = GestureDetector(window=5, min_votes=2, cooldown_s=1.5)
    first = detector.push_burst("wave", now=10.0)
    second = detector.push_burst("wave", now=10.5)
    third = detector.push_burst("wave", now=11.6)
    assert first is not None
    assert second is None
    assert third is not None


def test_different_actions_are_independent():
    detector = GestureDetector(window=5, min_votes=2, cooldown_s=1.5)
    assert detector.push_burst("wave", now=1.0) is not None
    assert detector.push_burst("right", now=1.1) is not None


def test_unknown_and_empty_gestures_are_ignored():
    detector = GestureDetector()
    assert detector.push("jump", now=1.0) is None
    assert detector.push(None, now=1.1) is None
    assert detector.push("", now=1.2) is None


def test_aliases_and_vote_distribution():
    assert normalize_gesture("挥手") == "wave"
    assert normalize_gesture("Circle CW") == "cw"
    assert normalize_gesture("clockwise") == "cw"
    assert normalize_gesture("unknown") is None
    distribution = vote_distribution(["wave", None, "wave", "right"])
    assert distribution["wave"] == 2
    assert distribution["right"] == 1


def test_approach_and_leave_hold():
    presence = PresenceDetector(
        approach_cm=60,
        leave_cm=300,
        leave_hold_s=60,
    )
    assert presence.update(100, now=0) is None
    approach = presence.update(50, now=1)
    assert approach is not None
    assert approach.type == "approach"
    assert approach.action == "wake"
    assert presence.update(40, now=2) is None
    assert presence.update(350, now=3) is None
    assert presence.update(350, now=62) is None
    leave = presence.update(350, now=64)
    assert leave is not None
    assert leave.type == "leave"
    assert leave.action == "rest"


def test_leave_hold_resets_when_user_returns():
    presence = PresenceDetector(
        approach_cm=60,
        leave_cm=300,
        leave_hold_s=60,
    )
    presence.update(50, now=0)
    presence.update(350, now=1)
    assert presence.update(100, now=30) is None
    assert presence.update(350, now=40) is None
    assert presence.update(350, now=99) is None
    leave = presence.update(350, now=101)
    assert leave is not None


def test_phone_edges_and_seed():
    presence = PresenceDetector()
    presence.seed_phone(False)
    place = presence.update_phone(True, now=1)
    assert place is not None
    assert place.type == "phone_place"
    assert presence.update_phone(True, now=2) is None
    take = presence.update_phone(False, now=3)
    assert take is not None
    assert take.type == "phone_take"


def test_first_phone_update_does_not_emit():
    presence = PresenceDetector()
    assert presence.update_phone(True, now=1) is None
    assert presence.update_phone(False, now=2) is not None


def test_presence_disabled_emits_nothing():
    presence = PresenceDetector(enabled=False)
    assert presence.update(10, now=1) is None
    assert presence.update_phone(True, now=2) is None
