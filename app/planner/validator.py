"""Consistency checks for generated plans.

The validator is deliberately independent from the scheduler so tests
can inject overlapping, over-capacity or overdue plans and prove that
the checks catch them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from planner.models import PlanDraft, Prefs, SubTask, Task
from planner.timeutil import at, ensure_aware, parse_hhmm

_CHINESE_VERBS = (
    "打开",
    "列出",
    "收集",
    "写出",
    "完成",
    "通读",
    "翻看",
    "读完",
    "读",
    "整理",
    "回看",
    "做",
    "拆分",
    "朗读",
    "编",
    "默写",
    "重做",
    "背诵",
    "复述",
    "阅读",
    "准备",
    "搭建",
    "写下",
    "形成",
    "模拟",
    "画出",
    "画",
    "搭好",
    "实现",
    "补齐",
    "运行",
    "拆解",
    "检查",
    "安排",
    "开始",
    "继续",
    "复习",
    "背",
    "练习",
    "制定",
    "计算",
    "推导",
    "分析",
    "总结",
    "修改",
    "提交",
    "发送",
    "联系",
    "购买",
    "查找",
    "下载",
    "上传",
    "打印",
    "填写",
    "观看",
    "听",
    "标记",
    "标注",
    "记录",
    "设计",
    "编写",
    "测试",
    "部署",
    "安装",
    "配置",
    "清理",
    "归档",
)
_ENGLISH_VERBS = (
    "open",
    "list",
    "read",
    "write",
    "draft",
    "collect",
    "gather",
    "complete",
    "finish",
    "review",
    "outline",
    "brainstorm",
    "research",
    "create",
    "build",
    "implement",
    "run",
    "test",
    "fix",
    "refactor",
    "prepare",
    "plan",
    "organize",
    "organise",
    "summarize",
    "summarise",
    "check",
    "submit",
    "send",
    "call",
    "email",
    "buy",
    "print",
    "fill",
    "watch",
    "listen",
    "label",
    "note",
    "record",
    "design",
    "code",
    "debug",
    "deploy",
    "install",
    "configure",
    "clean",
    "archive",
)
_WORD = re.compile(r"^[A-Za-z]+")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    ref: str = ""
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "ref": self.ref,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {issue.code for issue in self.issues}

    def raise_for_errors(self) -> None:
        if not self.ok:
            codes = ", ".join(sorted({issue.code for issue in self.errors}))
            raise PlanValidationError(
                f"plan validation failed: {codes}",
                self,
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class PlanValidationError(ValueError):
    def __init__(self, message: str, result: ValidationResult) -> None:
        super().__init__(message)
        self.result = result


def validate_plan(
    plan: PlanDraft,
    tasks: list[Task],
    prefs: Prefs | None = None,
    *,
    plan_date: date | None = None,
) -> ValidationResult:
    """Return every consistency issue in ``plan``."""
    prefs = prefs or Prefs()
    zone = prefs.tzinfo
    result = ValidationResult()
    try:
        day = date.fromisoformat(plan.date)
    except (TypeError, ValueError):
        _error(result, "invalid_date", f"invalid plan date {plan.date!r}")
        return result
    if plan_date is not None and day != plan_date:
        _error(result, "date_mismatch", "plan.date does not match plan_date")

    windows = prefs.windows_for(day)
    available = sum(window.duration_minutes for window in windows)
    task_by_id = {task.id: task for task in tasks}
    subtasks: dict[str, SubTask] = {}
    for task in tasks:
        for subtask in task.subtasks:
            subtasks[subtask.id] = subtask

    parsed: list[tuple[datetime, datetime, object]] = []
    seen_subtasks: set[str] = set()
    for item in plan.items:
        try:
            start = at(day, parse_hhmm(item.start), zone)
            end = at(day, parse_hhmm(item.end), zone)
        except (TypeError, ValueError):
            _error(
                result,
                "invalid_time",
                f"invalid time range {item.start}-{item.end}",
                item.subtask_id,
            )
            continue
        if end <= start:
            _error(
                result,
                "invalid_interval",
                f"{item.start}-{item.end} is not a positive interval",
                item.subtask_id,
            )
            continue
        actual = int(round((end - start).total_seconds() / 60.0))
        if actual != item.est_minutes:
            _error(
                result,
                "duration_mismatch",
                f"{item.subtask_id} spans {actual} min but "
                f"est_minutes={item.est_minutes}",
                item.subtask_id,
            )
        if actual < prefs.min_step_minutes or actual > prefs.max_step_minutes:
            _error(
                result,
                "step_duration",
                f"{item.subtask_id} is {actual} min, outside "
                f"{prefs.min_step_minutes}-{prefs.max_step_minutes}",
                item.subtask_id,
            )
        if not is_verb_first(item.title):
            _error(
                result,
                "not_verb_first",
                f"step does not start with a verb: {item.title!r}",
                item.subtask_id,
            )
        task = task_by_id.get(item.task_id)
        if task is None:
            _error(
                result,
                "unknown_task",
                f"unknown task {item.task_id!r}",
                item.subtask_id,
            )
        else:
            subtask = subtasks.get(item.subtask_id)
            if subtask is None:
                _error(
                    result,
                    "unknown_subtask",
                    f"unknown subtask {item.subtask_id!r}",
                    item.subtask_id,
                )
            elif subtask.task_id != item.task_id:
                _error(
                    result,
                    "subtask_task_mismatch",
                    f"{item.subtask_id} belongs to {subtask.task_id}, "
                    f"not {item.task_id}",
                    item.subtask_id,
                )
            if not _inside_windows(start, end, day, windows, zone):
                _error(
                    result,
                    "outside_available",
                    f"{item.start}-{item.end} is outside available windows",
                    item.subtask_id,
                )
            deadline = _deadline(task, zone)
            if deadline is not None and end > deadline:
                _error(
                    result,
                    "overdue",
                    f"{item.subtask_id} ends after task deadline "
                    f"{deadline.isoformat()}",
                    item.task_id,
                )
            if item.subtask_id in seen_subtasks:
                _error(
                    result,
                    "duplicate_subtask",
                    f"subtask {item.subtask_id!r} appears twice",
                    item.subtask_id,
                )
            seen_subtasks.add(item.subtask_id)
        parsed.append((start, end, item))

    _check_overlaps(result, parsed)
    _check_breaks(result, plan, day, windows, zone, parsed)
    _check_capacity(result, plan, available, parsed)
    _check_task_quality(result, plan, task_by_id, prefs, day, zone)
    _check_dependencies(result, plan, task_by_id, day, zone)
    return result


def is_verb_first(title: str) -> bool:
    """Heuristic machine check for the prompt rule 'start with a verb'."""
    text = (title or "").strip()
    if not text:
        return False
    for verb in _CHINESE_VERBS:
        if text.startswith(verb):
            return True
    match = _WORD.match(text)
    if match and match.group(0).lower() in _ENGLISH_VERBS:
        return True
    return False


def _inside_windows(
    start: datetime,
    end: datetime,
    day: date,
    windows,
    zone,
) -> bool:
    for window in windows:
        window_start = at(day, window.start, zone)
        window_end = at(day, window.end, zone)
        if start >= window_start and end <= window_end:
            return True
    return False


def _deadline(task: Task, zone) -> datetime | None:
    deadline = task.deadline_at
    if deadline is None:
        return None
    return ensure_aware(deadline, zone)


def _check_overlaps(result: ValidationResult, parsed: list[tuple]) -> None:
    ordered = sorted(parsed, key=lambda entry: entry[0])
    for index in range(1, len(ordered)):
        previous_end = ordered[index - 1][1]
        current_start = ordered[index][0]
        if current_start < previous_end:
            previous_item = ordered[index - 1][2]
            current_item = ordered[index][2]
            _error(
                result,
                "overlap",
                f"{previous_item.subtask_id} overlaps "
                f"{current_item.subtask_id}",
                current_item.subtask_id,
            )


def _check_breaks(
    result: ValidationResult,
    plan: PlanDraft,
    day: date,
    windows,
    zone,
    parsed: list[tuple],
) -> None:
    intervals: list[tuple[datetime, datetime]] = [
        (start, end) for start, end, _ in parsed
    ]
    break_intervals: list[tuple[datetime, datetime]] = []
    for entry in plan.breaks:
        try:
            start = at(day, parse_hhmm(entry.start), zone)
        except (TypeError, ValueError):
            _error(result, "invalid_time", f"invalid break {entry.start!r}")
            continue
        if entry.minutes <= 0:
            _error(
                result,
                "invalid_break",
                f"break at {entry.start} has {entry.minutes} minutes",
            )
            continue
        end = start + timedelta(minutes=entry.minutes)
        if not _inside_windows(start, end, day, windows, zone):
            _error(
                result,
                "break_outside",
                f"break at {entry.start} is outside available windows",
            )
        for item_start, item_end in intervals:
            if start < item_end and item_start < end:
                _error(
                    result,
                    "break_overlap",
                    f"break at {entry.start} overlaps a plan item",
                )
        for other_start, other_end in break_intervals:
            if start < other_end and other_start < end:
                _error(
                    result,
                    "break_overlap",
                    f"break at {entry.start} overlaps another break",
                )
        break_intervals.append((start, end))


def _check_capacity(
    result: ValidationResult,
    plan: PlanDraft,
    available: int,
    parsed: list[tuple],
) -> None:
    scheduled = 0
    for start, end, _ in parsed:
        scheduled += int(round((end - start).total_seconds() / 60.0))
    scheduled += sum(
        entry.minutes for entry in plan.breaks if entry.minutes > 0
    )
    if scheduled > available:
        _error(
            result,
            "capacity_exceeded",
            f"scheduled {scheduled} min exceeds {available} min available",
        )


def _check_task_quality(
    result: ValidationResult,
    plan: PlanDraft,
    task_by_id: dict[str, Task],
    prefs: Prefs,
    day: date,
    zone,
) -> None:
    for task_id, task in task_by_id.items():
        items = [item for item in plan.items if item.task_id == task_id]
        if not items:
            continue
        ordered = sorted(items, key=lambda item: item.start)
        first = ordered[0]
        if first.est_minutes > prefs.max_first_step_minutes:
            _error(
                result,
                "first_step_too_long",
                f"{task_id} starts with a {first.est_minutes} min step",
                task_id,
            )
        index = {
            subtask.id: position
            for position, subtask in enumerate(
                sorted(task.subtasks, key=lambda item: item.order)
            )
        }
        orders = [index.get(item.subtask_id, -1) for item in ordered]
        if any(value < 0 for value in orders):
            continue
        if orders != sorted(orders):
            _error(
                result,
                "subtask_out_of_order",
                f"{task_id} steps are not in dependency order",
                task_id,
            )

        focus_block = 0
        previous_end: datetime | None = None
        for item in ordered:
            try:
                start = at(day, parse_hhmm(item.start), zone)
                end = at(day, parse_hhmm(item.end), zone)
            except (TypeError, ValueError):
                continue
            if previous_end is not None and start > previous_end:
                focus_block = 0
            focus_block += item.est_minutes
            if focus_block > prefs.break_every_minutes + 10:
                _warning(
                    result,
                    "long_focus_block",
                    f"{task_id} has more than "
                    f"{prefs.break_every_minutes + 10} min without a break",
                    task_id,
                )
            previous_end = end


def _check_dependencies(
    result: ValidationResult,
    plan: PlanDraft,
    task_by_id: dict[str, Task],
    day: date,
    zone,
) -> None:
    items_by_task: dict[str, list[tuple[datetime, datetime]]] = {}
    for item in plan.items:
        try:
            start = at(day, parse_hhmm(item.start), zone)
            end = at(day, parse_hhmm(item.end), zone)
        except (TypeError, ValueError):
            continue
        items_by_task.setdefault(item.task_id, []).append((start, end))
    for task in task_by_id.values():
        items = items_by_task.get(task.id, [])
        if not items:
            continue
        first_start = min(start for start, _ in items)
        for dependency_id in task.depends_on:
            dependency = task_by_id.get(dependency_id)
            if dependency is None:
                continue
            dependency_items = items_by_task.get(dependency_id, [])
            if not dependency_items:
                _error(
                    result,
                    "dependency_missing",
                    f"{task.id} depends on {dependency_id}, "
                    "which has no planned steps",
                    task.id,
                )
                continue
            last_end = max(end for _, end in dependency_items)
            if first_start < last_end:
                _error(
                    result,
                    "dependency_violation",
                    f"{task.id} starts before {dependency_id} finishes",
                    task.id,
                )


def _error(
    result: ValidationResult,
    code: str,
    message: str,
    ref: str = "",
) -> None:
    result.issues.append(ValidationIssue(code, message, ref, "error"))


def _warning(
    result: ValidationResult,
    code: str,
    message: str,
    ref: str = "",
) -> None:
    result.issues.append(ValidationIssue(code, message, ref, "warning"))
