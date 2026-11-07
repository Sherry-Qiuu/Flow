"""Daily plan packing tests."""

from __future__ import annotations

import time
from datetime import date, datetime, time as clock
from datetime import timedelta

from planner import Prefs, RuleEngine, Task, TimeWindow
from planner.timeutil import parse_hhmm, tz_for

DAY = date(2026, 11, 8)
PREFS = Prefs(
    default_windows=(TimeWindow(clock(19, 0), clock(22, 0)),),
)


def parse_day(value: str) -> datetime:
    zone = tz_for(PREFS.timezone)
    return datetime.combine(DAY, parse_hhmm(value), tzinfo=zone)


def five_tasks() -> list[Task]:
    return [
        Task(
            id="t1",
            title="写课程论文提纲",
            est_minutes=60,
            deadline=datetime(2026, 11, 8, 23, 0),
            priority=1,
        ),
        Task(id="t2", title="读教材第 3 章", est_minutes=45, priority=2),
        Task(id="t3", title="背 50 个单词", est_minutes=30, priority=3),
        Task(id="t4", title="准备小组讨论", est_minutes=30, priority=3),
        Task(id="t5", title="整理实验数据", est_minutes=45, priority=2),
    ]


def assert_no_overlap(plan) -> None:
    entries = [
        (parse_day(item.start), parse_day(item.end))
        for item in plan.items
    ]
    entries.sort()
    for previous, current in zip(entries, entries[1:]):
        assert previous[1] <= current[0], (previous, current)


def test_five_messy_tasks_produce_valid_plan():
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, five_tasks())
    assert draft.items
    assert len({item.task_id for item in draft.items}) >= 3
    assert engine.last_validation is not None
    assert engine.last_validation.ok
    assert draft.total_minutes <= 180
    assert_no_overlap(draft)
    assert all(
        15 <= item.est_minutes <= 45 for item in draft.items
    )
    assert all(item.end > item.start for item in draft.items)


def test_plan_keeps_buffer_and_break_cadence():
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, five_tasks())
    assert draft.total_minutes <= int(180 * 0.8)
    assert draft.breaks
    assert all(entry.minutes == 10 for entry in draft.breaks)


def test_breaks_do_not_overlap_plan_items():
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, five_tasks())
    items = [
        (parse_day(item.start), parse_day(item.end))
        for item in draft.items
    ]
    for entry in draft.breaks:
        start = parse_day(entry.start)
        end = start + timedelta(minutes=entry.minutes)
        for item_start, item_end in items:
            assert not (start < item_end and item_start < end)


def test_plan_respects_deadline():
    task = Task(
        id="due",
        title="写课程论文提纲",
        est_minutes=60,
        deadline=datetime(2026, 11, 8, 20, 30),
        priority=1,
    )
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [task])
    assert draft.items
    for item in draft.items:
        assert parse_day(item.end) <= datetime(
            2026,
            11,
            8,
            20,
            30,
            tzinfo=tz_for(PREFS.timezone),
        )
    assert engine.last_validation.ok


def test_dependency_starts_after_prerequisite():
    prerequisite = Task(
        id="b",
        title="读教材第 3 章",
        est_minutes=45,
        priority=2,
    )
    dependent = Task(
        id="a",
        title="写课程论文提纲",
        est_minutes=60,
        priority=1,
        depends_on=("b",),
    )
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [dependent, prerequisite])
    b_items = [item for item in draft.items if item.task_id == "b"]
    a_items = [item for item in draft.items if item.task_id == "a"]
    assert b_items and a_items
    assert max(parse_day(item.end) for item in b_items) <= min(
        parse_day(item.start) for item in a_items
    )
    assert engine.last_validation.ok


def test_partial_prerequisite_blocks_dependent():
    prerequisite = Task(
        id="big",
        title="完成一个很大的项目",
        est_minutes=600,
        priority=1,
    )
    dependent = Task(
        id="after",
        title="写课程论文提纲",
        est_minutes=30,
        priority=1,
        depends_on=("big",),
    )
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [prerequisite, dependent])
    assert not any(item.task_id == "after" for item in draft.items)
    assert any("暂不安排" in warning for warning in draft.warnings)


def test_trimming_emits_warnings_but_preserves_invariants():
    tasks = [
        Task(
            id=f"t{index}",
            title=f"阅读第 {index} 章教材",
            est_minutes=120,
            priority=3,
        )
        for index in range(6)
    ]
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, tasks)
    assert draft.warnings
    assert draft.total_minutes <= 180
    assert engine.last_validation.ok
    assert_no_overlap(draft)


def test_no_windows_returns_empty_plan():
    prefs = Prefs(default_windows=())
    engine = RuleEngine(prefs)
    draft = engine.plan(DAY, [Task(id="t", title="写提纲")])
    assert draft.items == []
    assert draft.warnings


def test_completed_task_is_skipped():
    task = Task(
        id="done",
        title="写课程论文提纲",
        completed=True,
        est_minutes=30,
    )
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [task])
    assert draft.items == []
    assert "没有待安排的任务" in draft.warnings


def test_rule_engine_is_fast_enough_for_offline_fallback():
    engine = RuleEngine(PREFS)
    start = time.perf_counter()
    for _ in range(10):
        engine.plan(DAY, five_tasks())
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0


def test_plan_to_dict_matches_contract():
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, five_tasks())
    payload = draft.to_dict()
    assert set(payload) == {
        "plan_id",
        "date",
        "items",
        "breaks",
        "notes",
        "warnings",
        "mode",
    }
    assert payload["plan_id"] == "p_20261108"
    assert payload["date"] == "2026-11-08"
    for item in payload["items"]:
        assert set(item) == {
            "task_id",
            "subtask_id",
            "start",
            "end",
            "title",
            "est_minutes",
        }
    for note in payload["notes"]:
        assert set(note) == {"text", "ref"}


def test_energy_note_for_morning_and_evening_windows():
    prefs = Prefs(
        default_windows=(
            TimeWindow(clock(9, 0), clock(12, 0)),
            TimeWindow(clock(19, 0), clock(22, 0)),
        )
    )
    task = Task(id="long", title="完成一个很大的项目", est_minutes=300)
    draft = RuleEngine(prefs).plan(DAY, [task])
    assert any("上午" in note.text for note in draft.notes)


def test_plan_stays_inside_multiple_windows():
    prefs = Prefs(
        default_windows=(
            TimeWindow(clock(9, 0), clock(10, 0)),
            TimeWindow(clock(19, 0), clock(22, 0)),
        )
    )
    engine = RuleEngine(prefs)
    draft = engine.plan(
        DAY,
        [Task(id="long", title="完成一个很大的项目", est_minutes=300)],
    )
    assert draft.items
    for item in draft.items:
        start = parse_day(item.start)
        end = parse_day(item.end)
        assert any(
            start >= datetime.combine(
                DAY,
                window.start,
                tzinfo=tz_for(prefs.timezone),
            )
            and end <= datetime.combine(
                DAY,
                window.end,
                tzinfo=tz_for(prefs.timezone),
            )
            for window in prefs.default_windows
        )
    assert engine.last_validation.ok


def test_past_deadline_is_not_scheduled():
    task = Task(
        id="late",
        title="写课程论文提纲",
        est_minutes=60,
        deadline=datetime(2026, 11, 8, 18, 0),
    )
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [task])
    assert draft.items == []
    assert any("未安排" in warning for warning in draft.warnings)


def test_oversized_task_is_reported_as_capped():
    task = Task(id="huge", title="完成一个很大的项目", est_minutes=600)
    engine = RuleEngine(PREFS)
    draft = engine.plan(DAY, [task])
    assert any("拆解上限" in warning for warning in draft.warnings)
