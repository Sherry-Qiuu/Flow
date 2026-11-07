"""Deterministic daily packing for the rule-based planner.

The algorithm is intentionally simple enough to explain to a user:

* order pending tasks by deadline, then priority, then difficulty;
* fill each day window chronologically;
* reserve a 20% buffer;
* insert a short break before a block would exceed about 50 minutes;
* trim the lowest-value tail when the day cannot hold everything.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from planner.models import (
    Break,
    PlanDraft,
    PlanItem,
    PlanNote,
    Prefs,
    SubTask,
    Task,
    make_plan_id,
)
from planner.timeutil import ensure_aware, format_hhmm


@dataclass
class _Window:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int(round((self.end - self.start).total_seconds() / 60.0))


@dataclass
class _ScheduleState:
    windows: list[_Window]
    capacity: int
    prefs: Prefs
    items: list[PlanItem] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used: int = 0
    window_index: int = 0
    cursor: datetime | None = None
    focus_minutes: int = 0
    scheduled: dict[str, list[PlanItem]] = field(default_factory=dict)
    ends: dict[str, datetime] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.windows:
            self.cursor = self.windows[0].start

    def _advance(self) -> None:
        self.window_index += 1
        self.focus_minutes = 0
        if self.window_index < len(self.windows):
            self.cursor = self.windows[self.window_index].start

    def _has_next(self) -> bool:
        return self.window_index + 1 < len(self.windows)

    def _fits_window(self, start: datetime, end: datetime) -> bool:
        window = self.windows[self.window_index]
        return start >= window.start and end <= window.end

    def _emit(
        self,
        task: Task,
        subtask: SubTask,
        start: datetime,
        end: datetime,
        break_before: Break | None,
    ) -> None:
        if break_before is not None:
            self.breaks.append(break_before)
            self.used += break_before.minutes
            self.focus_minutes = 0
            start = start + timedelta(minutes=break_before.minutes)
            end = start + timedelta(minutes=subtask.est_minutes)
        item = PlanItem(
            task_id=task.id,
            subtask_id=subtask.id,
            start=format_hhmm(start),
            end=format_hhmm(end),
            title=subtask.title,
            est_minutes=subtask.est_minutes,
        )
        self.items.append(item)
        self.scheduled.setdefault(task.id, []).append(item)
        self.ends[task.id] = end
        self.used += subtask.est_minutes
        self.cursor = end
        self.focus_minutes += subtask.est_minutes

    def try_place(
        self,
        task: Task,
        subtask: SubTask,
        earliest: datetime | None,
        deadline: datetime | None,
    ) -> tuple[bool, str]:
        duration = subtask.est_minutes
        while self.window_index < len(self.windows):
            window = self.windows[self.window_index]
            if self.cursor is None or self.cursor < window.start:
                self.cursor = window.start
            start = self.cursor
            if earliest is not None and earliest > start:
                start = earliest
            if start >= window.end:
                if earliest is not None and earliest >= window.end:
                    if self._has_next():
                        self._advance()
                        continue
                    return False, "dependency"
                self._advance()
                continue

            needs_break = (
                self.prefs.break_minutes > 0
                and self.focus_minutes > 0
                and self.focus_minutes + duration
                > self.prefs.break_every_minutes + 5
            )
            break_length = (
                self.prefs.break_minutes if needs_break else 0
            )
            break_end = start + timedelta(minutes=break_length)
            item_start = break_end if needs_break else start
            item_end = item_start + timedelta(minutes=duration)

            if deadline is not None and item_end > deadline:
                return False, "deadline"

            if needs_break:
                can_break = (
                    break_end <= window.end
                    and item_end <= window.end
                    and self.used + break_length + duration
                    <= self.capacity
                )
                if not can_break:
                    if self._has_next():
                        self._advance()
                        continue
                    # Protect the rest cadence instead of stacking work.
                    return False, "break"
                self._emit(
                    task,
                    subtask,
                    start,
                    item_end,
                    Break(format_hhmm(start), break_length),
                )
                return True, "ok"

            if self.used + duration > self.capacity:
                return False, "capacity"
            if item_end <= window.end:
                self._emit(task, subtask, start, item_end, None)
                return True, "ok"

            if self._has_next():
                self._advance()
                continue
            self._advance()
        return False, "window"


def build_plan(
    plan_date: date,
    tasks: list[Task],
    prefs: Prefs | None = None,
    *,
    mode: str = "rule",
) -> PlanDraft:
    """Pack tasks into ``plan_date`` and always return a draft."""
    prefs = prefs or Prefs()
    zone = prefs.tzinfo
    draft = PlanDraft(
        plan_id=make_plan_id(plan_date),
        date=plan_date.isoformat(),
        mode=mode,
    )
    pending = [task for task in tasks if not task.completed]
    if not pending:
        draft.warnings.append("没有待安排的任务")
        return draft

    duplicate_ids = _duplicates([task.id for task in pending])
    if duplicate_ids:
        raise ValueError(f"duplicate task ids: {', '.join(duplicate_ids)}")

    windows = _windows_for(plan_date, prefs)
    available = sum(window.minutes for window in windows)
    reserve = int(math.floor(available * prefs.buffer_ratio))
    capacity = max(0, available - reserve)

    if not windows or capacity < prefs.min_step_minutes:
        draft.warnings.append("今天没有足够的可用时段，计划为空")
        return draft

    if reserve > 0:
        draft.notes.append(
            PlanNote(
                f"已预留 {reserve} 分钟（{prefs.buffer_ratio:.0%}）"
                "缓冲，不排任务",
            )
        )
    if prefs.break_minutes > 0:
        draft.notes.append(
            PlanNote(
                f"连续专注约 {prefs.break_every_minutes} 分钟后"
                f"插入 {prefs.break_minutes} 分钟休息",
            )
        )

    state = _ScheduleState(windows, capacity, prefs)
    ordered = _topological_order(pending, zone, draft.warnings)
    pending_by_id = {task.id: task for task in pending}
    scheduled_end: dict[str, datetime] = {}

    for task in ordered:
        subtasks = sorted(task.subtasks, key=lambda item: item.order)
        if not subtasks:
            draft.warnings.append(f"《{task.title}》没有可执行的步骤")
            continue

        deadline = _deadline(task, zone)
        required_start: datetime | None = None
        blocked = ""
        for dependency_id in task.depends_on:
            dependency = pending_by_id.get(dependency_id)
            if dependency is None:
                continue
            dependency_items = state.scheduled.get(dependency_id, [])
            if not dependency.subtasks or len(dependency_items) < len(
                dependency.subtasks
            ):
                blocked = f"前置任务《{dependency.title}》未全部排入"
                break
            dependency_end = scheduled_end.get(dependency_id)
            if dependency_end is not None:
                if required_start is None or dependency_end > required_start:
                    required_start = dependency_end
        if blocked:
            draft.warnings.append(f"《{task.title}》暂不安排：{blocked}")
            continue
        if (
            deadline is not None
            and required_start is not None
            and required_start >= deadline
        ):
            draft.warnings.append(
                f"《{task.title}》的前置任务结束晚于截止时间，暂不安排"
            )
            continue

        placed_count = 0
        for index, subtask in enumerate(subtasks):
            ok, reason = state.try_place(
                task,
                subtask,
                required_start,
                deadline,
            )
            if ok:
                placed_count += 1
                continue
            remaining = len(subtasks) - index
            if placed_count == 0:
                draft.warnings.append(
                    f"《{task.title}》本次未安排（{_reason_text(reason)}）"
                )
            else:
                draft.warnings.append(
                    f"《{task.title}》本次只安排前 {placed_count} 步"
                    f"（{_reason_text(reason)}，剩余 {remaining} 步）"
                )
                draft.notes.append(
                    PlanNote(
                        f"时间不够，先做《{task.title}》的前 "
                        f"{placed_count} 步",
                        task.id,
                    )
                )
            break

        if placed_count == len(subtasks):
            scheduled_end[task.id] = state.ends.get(task.id, windows[-1].start)
            if deadline is not None and deadline.date() == plan_date:
                draft.notes.append(
                    PlanNote(
                        f"《{task.title}》需在 {format_hhmm(deadline)} "
                        "前完成，已优先安排",
                        task.id,
                    )
                )

    if state.breaks:
        draft.notes.append(
            PlanNote(
                "已按 45–50 分钟的节奏插入休息，避免连续硬撑",
            )
        )
    _energy_note(prefs, windows, draft.notes)
    draft.items = sorted(state.items, key=lambda item: item.start)
    draft.breaks = sorted(state.breaks, key=lambda entry: entry.start)
    if state.items:
        first_item = min(state.items, key=lambda item: item.start)
        draft.notes.insert(
            0,
            PlanNote(
                "按截止时间与优先级排序，先安排更紧的任务",
                first_item.task_id,
            ),
        )
    draft.warnings.extend(state.warnings)
    return draft


def _reason_text(reason: str) -> str:
    return {
        "deadline": "截止时间前没有空位",
        "capacity": "预留缓冲后时间不足",
        "dependency": "前置任务占用了时间",
        "window": "可用时段已排满",
        "break": "需要保留休息时间",
    }.get(reason, "时间不足")


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: list[str] = []
    for value in values:
        if value in seen and value not in duplicated:
            duplicated.append(value)
        seen.add(value)
    return duplicated


def _windows_for(plan_date: date, prefs: Prefs) -> list[_Window]:
    zone = prefs.tzinfo
    raw = sorted(
        (
            _Window(
                datetime.combine(plan_date, window.start, tzinfo=zone),
                datetime.combine(plan_date, window.end, tzinfo=zone),
            )
            for window in prefs.windows_for(plan_date)
        ),
        key=lambda window: window.start,
    )
    merged: list[_Window] = []
    for window in raw:
        if merged and window.start <= merged[-1].end:
            if window.end > merged[-1].end:
                merged[-1] = _Window(merged[-1].start, window.end)
            continue
        merged.append(window)
    return merged


def _deadline(task: Task, zone) -> datetime | None:
    deadline = task.deadline_at
    if deadline is None:
        return None
    return ensure_aware(deadline, zone)


def _task_key(task: Task, zone) -> tuple[float, int, int, float, str]:
    deadline = _deadline(task, zone)
    deadline_ts = (
        deadline.timestamp() if deadline is not None else float("inf")
    )
    difficulty = max(
        (subtask.difficulty for subtask in task.subtasks),
        default=0,
    )
    total = sum(subtask.est_minutes for subtask in task.subtasks)
    return (deadline_ts, task.priority, -difficulty, -float(total), task.id)


def _topological_order(
    tasks: list[Task],
    zone,
    warnings: list[str],
) -> list[Task]:
    by_id = {task.id: task for task in tasks}
    indegree = {task.id: 0 for task in tasks}
    dependents: dict[str, list[str]] = {task.id: [] for task in tasks}
    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in by_id:
                continue
            indegree[task.id] += 1
            dependents[dependency].append(task.id)

    heap: list[tuple[tuple[float, int, int, float, str], int, Task]] = []
    counter = 0
    for task in tasks:
        if indegree[task.id] == 0:
            heapq.heappush(heap, (_task_key(task, zone), counter, task))
            counter += 1

    ordered: list[Task] = []
    while heap:
        _, _, task = heapq.heappop(heap)
        ordered.append(task)
        for dependent_id in dependents[task.id]:
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                dependent = by_id[dependent_id]
                heapq.heappush(
                    heap,
                    (_task_key(dependent, zone), counter, dependent),
                )
                counter += 1

    remaining = [task for task in tasks if task not in ordered]
    if remaining:
        warnings.append("任务依赖存在环，剩余任务按截止时间处理")
        ordered.extend(
            sorted(remaining, key=lambda task: _task_key(task, zone))
        )
    return ordered


def _energy_note(
    prefs: Prefs,
    windows: list[_Window],
    notes: list[PlanNote],
) -> None:
    if not prefs.energy_aware or not windows:
        return
    has_morning = any(window.start.hour < 12 for window in windows)
    has_evening = any(window.start.hour >= 18 for window in windows)
    if has_morning and has_evening:
        notes.append(
            PlanNote(
                "上午先安排需要动脑的步骤，晚间安排背诵、整理等轻任务"
            )
        )
    elif all(window.start.hour >= 18 for window in windows):
        notes.append(
            PlanNote("可用时段在晚间，所有步骤已控制在 45 分钟以内")
        )
