"""Validator tests, including injected bad plans."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time as clock

import pytest

from planner import (
    PlanDraft,
    PlanItem,
    Prefs,
    RuleEngine,
    SubTask,
    Task,
    TimeWindow,
    validate_plan,
)
from planner.validator import PlanValidationError

DAY = date(2026, 11, 8)
PREFS = Prefs(
    default_windows=(TimeWindow(clock(19, 0), clock(22, 0)),),
)


def build_valid():
    task = Task(
        id="t1",
        title="写课程论文提纲",
        est_minutes=60,
        deadline=datetime(2026, 11, 8, 23, 0),
    )
    engine = RuleEngine(PREFS)
    plan = engine.plan(DAY, [task])
    prepared = replace(task, subtasks=engine.decompose(task))
    result = validate_plan(plan, [prepared], PREFS, plan_date=DAY)
    assert result.ok, result.to_dict()
    assert plan.items
    return plan, prepared


def test_valid_plan_passes():
    plan, task = build_valid()
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert result.ok
    assert result.errors == []


def test_injected_overlap_is_caught():
    plan, task = build_valid()
    first = plan.items[0]
    plan.items[1] = replace(
        plan.items[1],
        start=first.start,
        end=first.end,
    )
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert not result.ok
    assert "overlap" in result.codes()


def test_injected_overdue_is_caught():
    plan, task = build_valid()
    late_task = replace(
        task,
        deadline=datetime(2026, 11, 8, 19, 10),
    )
    result = validate_plan(plan, [late_task], PREFS, plan_date=DAY)
    assert not result.ok
    assert "overdue" in result.codes()


def test_item_outside_window_is_caught():
    plan, task = build_valid()
    plan.items[-1] = replace(
        plan.items[-1],
        start="22:30",
        end="22:50",
    )
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert not result.ok
    assert "outside_available" in result.codes()


def test_over_capacity_plan_is_caught():
    subtasks = [
        SubTask(
            id=f"t_s{index}",
            task_id="t",
            title="阅读第 1 节教材",
            est_minutes=45,
            order=index,
        )
        for index in range(1, 6)
    ]
    task = Task(id="t", title="读教材", subtasks=subtasks)
    items = [
        PlanItem(
            task_id="t",
            subtask_id=f"t_s{index}",
            start=start,
            end=end,
            title="阅读第 1 节教材",
            est_minutes=45,
        )
        for index, (start, end) in enumerate(
            [
                ("19:00", "19:45"),
                ("19:45", "20:30"),
                ("20:30", "21:15"),
                ("21:15", "22:00"),
                ("22:00", "22:45"),
            ],
            start=1,
        )
    ]
    plan = PlanDraft(
        plan_id="p_20261108",
        date="2026-11-08",
        items=items,
    )
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert "capacity_exceeded" in result.codes()


def test_break_overlap_is_caught():
    plan, task = build_valid()
    assert plan.breaks
    plan.breaks[0] = replace(
        plan.breaks[0],
        start=plan.items[0].start,
    )
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert "break_overlap" in result.codes()


def test_non_verb_title_is_caught():
    plan, task = build_valid()
    plan.items[0] = replace(
        plan.items[0],
        title="为论文写提纲",
    )
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert "not_verb_first" in result.codes()


def test_unknown_task_is_caught():
    plan, task = build_valid()
    plan.items[0] = replace(plan.items[0], task_id="missing")
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    assert "unknown_task" in result.codes()


def test_dependency_violation_is_caught():
    sub_b = SubTask(
        id="b_s1",
        task_id="b",
        title="阅读教材一节",
        est_minutes=15,
        order=1,
    )
    sub_a = SubTask(
        id="a_s1",
        task_id="a",
        title="写出论文提纲",
        est_minutes=15,
        order=1,
    )
    task_b = Task(id="b", title="读教材", subtasks=[sub_b])
    task_a = Task(
        id="a",
        title="写提纲",
        depends_on=("b",),
        subtasks=[sub_a],
    )
    items = [
        PlanItem(
            task_id="a",
            subtask_id="a_s1",
            start="19:00",
            end="19:15",
            title="写出论文提纲",
            est_minutes=15,
        ),
        PlanItem(
            task_id="b",
            subtask_id="b_s1",
            start="19:15",
            end="19:30",
            title="阅读教材一节",
            est_minutes=15,
        ),
    ]
    plan = PlanDraft(
        plan_id="p_20261108",
        date="2026-11-08",
        items=items,
    )
    result = validate_plan(plan, [task_a, task_b], PREFS, plan_date=DAY)
    assert "dependency_violation" in result.codes()


def test_date_mismatch_is_caught():
    plan, task = build_valid()
    result = validate_plan(
        plan,
        [task],
        PREFS,
        plan_date=date(2026, 11, 9),
    )
    assert "date_mismatch" in result.codes()


def test_empty_plan_is_valid():
    plan = PlanDraft(plan_id="p_20261108", date="2026-11-08")
    result = validate_plan(plan, [], PREFS, plan_date=DAY)
    assert result.ok


def test_validation_error_can_be_raised():
    plan, task = build_valid()
    plan.items[0] = replace(plan.items[0], title="为论文写提纲")
    result = validate_plan(plan, [task], PREFS, plan_date=DAY)
    with pytest.raises(PlanValidationError) as raised:
        result.raise_for_errors()
    assert raised.value.result is result
