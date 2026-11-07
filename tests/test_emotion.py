"""T16/T17 celebration and companion tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from bus.local import LocalEventBus
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from emotion.celebrate import CelebrateService
from emotion.companion import CompanionService, LEVEL_THRESHOLDS
from emotion.phrases import FORBIDDEN, PHRASES, check_phrase, pick_phrase
from planner.timeutil import tz_for

TZ = tz_for("Asia/Shanghai")


class FakeSay:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def say(self, text, **_):
        self.calls.append(text)


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"emotion-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_phrases_are_safe_and_non_repeating():
    assert len(PHRASES) >= 20
    assert all(check_phrase(phrase) for phrase in PHRASES)
    assert not any(word in " ".join(PHRASES) for word in FORBIDDEN)
    first = pick_phrase("")
    second = pick_phrase(first)
    assert second != first


def test_companion_growth_and_no_penalty(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    companion = CompanionService(repos)
    assert companion.state()["level"] == 0
    for _ in range(10):
        companion.award("step_done")
    assert companion.state()["exp"] == 10
    assert companion.state()["level"] == 1
    companion.award("task_done")
    assert companion.state()["exp"] == 15
    # Missing days never subtracts experience.
    assert companion.state()["exp"] >= 15
    assert companion.state()["stage"] in ("幼芽", "小苗", "小树", "花期", "大树")
    database.close()


def test_celebrate_merges_and_quiet_night(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    bus = LocalEventBus()
    feedback = []
    bus.subscribe("reward.feedback", feedback.append)
    say = FakeSay()
    service = CelebrateService(
        CompanionService(repos, publisher=bus),
        publisher=bus,
        say=say,
        subscriber=bus,
    )
    service.start()
    try:
        for _ in range(5):
            service.celebrate("step_done")
        assert feedback[-1]["merged"] is True
        night = service.celebrate(
            "step_done",
            now=datetime(2026, 11, 7, 23, 0, tzinfo=TZ),
        )
        assert night["night"] is True
        assert say.calls
    finally:
        service.stop()
        database.close()
