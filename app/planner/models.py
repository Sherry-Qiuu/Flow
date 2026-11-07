"""Domain models for task decomposition and daily planning.

These are deliberately plain dataclasses so T10 can map its SQLModel
records onto them without a dependency cycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
from enum import Enum
from typing import Any

from planner.timeutil import parse_hhmm, tz_for


class Category(str, Enum):
    READING = "reading"
    WRITING = "writing"
    MEMORIZATION = "memorization"
    EXPERIMENT = "experiment"
    DISCUSSION = "discussion"
    CODING = "coding"
    # Drills and mistakes are their own shape of work: read the question,
    # answer, check, fix the wrong ones. Forcing them into WRITING produced
    # 「打开文档，列出 3 个核心论点」 for 「刷两套四级真题」.
    PRACTICE = "practice"
    PRESENTATION = "presentation"
    GENERAL = "general"


@dataclass(frozen=True)
class TimeWindow:
    start: time
    end: time

    def __post_init__(self) -> None:
        if not isinstance(self.start, time) or not isinstance(self.end, time):
            raise TypeError("window start and end must be datetime.time")
        if self.end <= self.start:
            raise ValueError("window end must be after start")

    @property
    def duration_minutes(self) -> int:
        start = self.start.hour * 60 + self.start.minute
        end = self.end.hour * 60 + self.end.minute
        return end - start

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
        }

    @classmethod
    def parse(cls, value: str) -> "TimeWindow":
        start_text, end_text = value.replace("\u2013", "-").split("-", 1)
        return cls(parse_hhmm(start_text), parse_hhmm(end_text))


@dataclass(frozen=True)
class Prefs:
    timezone: str = "Asia/Shanghai"
    default_windows: tuple[TimeWindow, ...] = (
        TimeWindow(time(19, 0), time(22, 0)),
    )
    windows_by_date: Mapping[date, tuple[TimeWindow, ...]] = field(
        default_factory=dict
    )
    buffer_ratio: float = 0.2
    break_every_minutes: int = 45
    break_minutes: int = 10
    min_step_minutes: int = 15
    max_step_minutes: int = 45
    max_first_step_minutes: int = 20
    min_steps: int = 3
    max_steps: int = 7
    energy_aware: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.buffer_ratio < 1.0:
            raise ValueError("buffer_ratio must be in [0, 1)")
        if self.break_every_minutes < 10:
            raise ValueError("break_every_minutes must be at least 10")
        if self.break_minutes < 0:
            raise ValueError("break_minutes must be non-negative")
        if self.min_step_minutes <= 0:
            raise ValueError("min_step_minutes must be positive")
        if self.max_step_minutes < self.min_step_minutes:
            raise ValueError("max_step_minutes must be >= min_step_minutes")
        if not 0 < self.max_first_step_minutes <= self.max_step_minutes:
            raise ValueError("max_first_step_minutes is out of range")
        if self.max_first_step_minutes < self.min_step_minutes:
            raise ValueError(
                "max_first_step_minutes must be >= min_step_minutes"
            )
        if not 1 <= self.min_steps <= self.max_steps <= 7:
            raise ValueError("step counts must satisfy 1 <= min <= max <= 7")

    @property
    def tzinfo(self) -> tzinfo:
        return tz_for(self.timezone)

    def windows_for(self, day: date) -> tuple[TimeWindow, ...]:
        return tuple(self.windows_by_date.get(day, self.default_windows))


@dataclass(frozen=True)
class SubTask:
    id: str
    task_id: str
    title: str
    est_minutes: int
    completion_criteria: str = ""
    depends_on: tuple[str, ...] = ()
    order: int = 0
    difficulty: int = 2
    source: str = "rule"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("subtask id is required")
        if not self.task_id:
            raise ValueError("subtask task_id is required")
        if not self.title.strip():
            raise ValueError("subtask title is required")
        if self.est_minutes <= 0:
            raise ValueError("subtask est_minutes must be positive")
        if not 1 <= self.difficulty <= 3:
            raise ValueError("subtask difficulty must be 1..3")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "est_minutes": self.est_minutes,
            "completion_criteria": self.completion_criteria,
            "depends_on": list(self.depends_on),
            "order": self.order,
            "difficulty": self.difficulty,
            "source": self.source,
        }


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    category: Category | None = None
    est_minutes: int | None = None
    deadline: datetime | date | None = None
    priority: int = 3
    depends_on: tuple[str, ...] = ()
    subtasks: list[SubTask] = field(default_factory=list)
    created_at: datetime | None = None
    completed: bool = False
    source: str = "manual"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("task id is required")
        if not self.title.strip():
            raise ValueError("task title is required")
        if isinstance(self.category, str):
            self.category = Category(self.category)
        if self.est_minutes is not None and self.est_minutes <= 0:
            raise ValueError("task est_minutes must be positive")
        if isinstance(self.deadline, date) and not isinstance(
            self.deadline, datetime
        ):
            self.deadline = datetime.combine(
                self.deadline,
                time(23, 59),
            )
        if not 1 <= self.priority <= 5:
            raise ValueError("task priority must be 1..5")
        self.depends_on = tuple(self.depends_on)
        self.subtasks = list(self.subtasks)

    @property
    def deadline_at(self) -> datetime | None:
        return self.deadline if isinstance(self.deadline, datetime) else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value if self.category else None,
            "est_minutes": self.est_minutes,
            "deadline": (
                self.deadline.isoformat()
                if isinstance(self.deadline, datetime)
                else None
            ),
            "priority": self.priority,
            "depends_on": list(self.depends_on),
            "subtasks": [subtask.to_dict() for subtask in self.subtasks],
            "completed": self.completed,
            "source": self.source,
        }


@dataclass(frozen=True)
class PlanItem:
    task_id: str
    subtask_id: str
    start: str
    end: str
    title: str
    est_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "est_minutes": self.est_minutes,
        }


@dataclass(frozen=True)
class Break:
    start: str
    minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "minutes": self.minutes}


@dataclass(frozen=True)
class PlanNote:
    text: str
    ref: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "ref": self.ref}


@dataclass
class PlanDraft:
    plan_id: str
    date: str
    items: list[PlanItem] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    notes: list[PlanNote] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "rule"

    @property
    def focus_minutes(self) -> int:
        return sum(item.est_minutes for item in self.items)

    @property
    def break_minutes(self) -> int:
        return sum(entry.minutes for entry in self.breaks)

    @property
    def total_minutes(self) -> int:
        return self.focus_minutes + self.break_minutes

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "date": self.date,
            "items": [item.to_dict() for item in self.items],
            "breaks": [entry.to_dict() for entry in self.breaks],
            "notes": [note.to_dict() for note in self.notes],
            "warnings": list(self.warnings),
            "mode": self.mode,
        }


def make_plan_id(day: date) -> str:
    return f"p_{day.strftime('%Y%m%d')}"


def day_bounds(day: date, tzinfo: tzinfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0, 0), tzinfo=tzinfo)
    return start, start + timedelta(days=1)
