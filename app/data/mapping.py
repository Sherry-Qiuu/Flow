"""Bidirectional mapping between planner dataclasses and SQLite rows."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from typing import Any

from planner.models import (
    Break,
    Category,
    PlanDraft,
    PlanItem,
    PlanNote,
    SubTask,
    Task,
    day_bounds,
)
from planner.timeutil import default_tz, parse_hhmm


def task_to_row(task: Task, user_id: str) -> dict[str, Any]:
    created = task.created_at or datetime.now(timezone.utc)
    created_utc = _to_utc(created)
    return {
        "id": task.id,
        "user_id": user_id,
        "title": task.title,
        "note": task.description,
        "source": task.source or "manual",
        "status": "done" if task.completed else "pending",
        "est_minutes": task.est_minutes,
        "due_at": _to_utc(task.deadline) if task.deadline else None,
        "priority": task.priority,
        "category": task.category.value if task.category else None,
        "depends_on_json": json.dumps(
            list(task.depends_on),
            ensure_ascii=False,
        ),
        "created_at": created_utc,
        "updated_at": created_utc,
        "deleted_at": None,
    }


def task_from_row(row: Any) -> Task:
    data = dict(row)
    deadline = _from_utc(data.get("due_at"))
    category = data.get("category")
    return Task(
        id=data["id"],
        title=data["title"],
        description=data.get("note", ""),
        category=Category(category) if category else None,
        est_minutes=data.get("est_minutes"),
        deadline=deadline,
        priority=int(data.get("priority", 3)),
        depends_on=tuple(
            json.loads(data.get("depends_on_json") or "[]")
        ),
        created_at=_from_utc(data.get("created_at")),
        completed=data.get("status") == "done",
        source=data.get("source", "manual"),
    )


def subtask_to_row(subtask: SubTask) -> dict[str, Any]:
    return {
        "id": subtask.id,
        "task_id": subtask.task_id,
        "title": subtask.title,
        "est_minutes": subtask.est_minutes,
        "order_index": subtask.order,
        "done_at": None,
        "completion_criteria": subtask.completion_criteria,
        "depends_on_json": json.dumps(
            list(subtask.depends_on),
            ensure_ascii=False,
        ),
        "difficulty": subtask.difficulty,
        "source": subtask.source,
        "created_at": _utc_now(),
    }


def subtask_from_row(row: Any) -> SubTask:
    data = dict(row)
    return SubTask(
        id=data["id"],
        task_id=data["task_id"],
        title=data["title"],
        est_minutes=int(data["est_minutes"]),
        completion_criteria=data.get("completion_criteria", ""),
        depends_on=tuple(
            json.loads(data.get("depends_on_json") or "[]")
        ),
        order=int(data.get("order_index", 0)),
        difficulty=int(data.get("difficulty", 2)),
        source=data.get("source", "rule"),
    )


def plan_to_row(draft: PlanDraft, user_id: str) -> dict[str, Any]:
    now = _utc_now()
    return {
        "id": draft.plan_id,
        "user_id": user_id,
        "plan_date": draft.date,
        "status": "draft",
        "version": 1,
        "breaks_json": json.dumps(
            [entry.to_dict() for entry in draft.breaks],
            ensure_ascii=False,
        ),
        "notes_json": json.dumps(
            [note.to_dict() for note in draft.notes],
            ensure_ascii=False,
        ),
        "warnings_json": json.dumps(
            list(draft.warnings),
            ensure_ascii=False,
        ),
        "mode": draft.mode,
        "created_at": now,
        "updated_at": now,
    }


def plan_item_to_row(
    item: PlanItem,
    plan_id: str,
    *,
    plan_date: str,
    order_index: int,
) -> dict[str, Any]:
    day = date.fromisoformat(plan_date)
    start = _local_clock_to_utc(day, item.start)
    end = _local_clock_to_utc(day, item.end)
    return {
        "id": f"{plan_id}_i{order_index}",
        "plan_id": plan_id,
        "task_id": item.task_id or None,
        "subtask_id": item.subtask_id or None,
        "start_at": start,
        "end_at": end,
        "order_index": order_index,
        "status": "pending",
        "title": item.title,
        "est_minutes": item.est_minutes,
    }


def plan_from_rows(plan_row: Any, item_rows: list[Any]) -> PlanDraft:
    plan = dict(plan_row)
    items = [
        PlanItem(
            task_id=row["task_id"] or "",
            subtask_id=row["subtask_id"] or "",
            start=_utc_to_local_clock(row["start_at"]),
            end=_utc_to_local_clock(row["end_at"]),
            title=row["title"],
            est_minutes=int(row["est_minutes"]),
        )
        for row in item_rows
    ]
    return PlanDraft(
        plan_id=plan["id"],
        date=plan["plan_date"],
        items=items,
        breaks=[
            Break(**entry)
            for entry in json.loads(plan.get("breaks_json") or "[]")
        ],
        notes=[
            PlanNote(**entry)
            for entry in json.loads(plan.get("notes_json") or "[]")
        ],
        warnings=list(json.loads(plan.get("warnings_json") or "[]")),
        mode=plan.get("mode", "rule"),
    )


def _to_utc(value: datetime | date) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time(23, 59), tzinfo=default_tz())
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_tz())
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _from_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(default_tz())


def _local_clock_to_utc(day: date, clock: str) -> str:
    local = datetime.combine(day, parse_hhmm(clock), tzinfo=default_tz())
    return local.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _utc_to_local_clock(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(default_tz()).strftime("%H:%M")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


__all__ = [
    "default_tz",
    "day_bounds",
    "plan_from_rows",
    "plan_item_to_row",
    "plan_to_row",
    "subtask_from_row",
    "subtask_to_row",
    "task_from_row",
    "task_to_row",
]
