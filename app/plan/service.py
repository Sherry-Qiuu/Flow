"""T13 plan negotiation, versioning and conflict detection."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Any

from bus import topics
from data.repositories import Repositories
from planner.engine import RuleEngine
from planner.models import PlanDraft, PlanItem, Task
from planner.timeutil import parse_hhmm

logger = logging.getLogger(__name__)


class PlanService:
    def __init__(
        self,
        repos: Repositories,
        *,
        publisher: Any = None,
        engine: RuleEngine | None = None,
    ) -> None:
        self.repos = repos
        self.publisher = publisher
        self.engine = engine or RuleEngine()
        self._versions: dict[str, list[PlanDraft]] = {}

    def create(
        self,
        tasks: list[Task],
        *,
        day: date | None = None,
    ) -> PlanDraft:
        plan_date = day or date.today()
        draft = self.engine.plan(plan_date, tasks)
        self._persist_subtasks(draft)
        self.repos.plans.save(draft)
        self._versions.setdefault(draft.plan_id, []).append(
            _copy(draft)
        )
        self._publish(topics.PLAN_DRAFT, draft.to_dict())
        return draft

    def create_from_repo(self, day: date | None = None) -> PlanDraft:
        tasks = self.repos.tasks.list()
        return self.create(tasks, day=day)

    def get(self, plan_id: str) -> PlanDraft | None:
        return self.repos.plans.get(plan_id)

    def revise(
        self,
        plan_id: str,
        instruction: str,
    ) -> dict[str, Any]:
        draft = self.repos.plans.get(plan_id)
        if draft is None:
            return {"ok": False, "reason": "plan not found"}
        before = _copy(draft)
        changed = _apply_instruction(draft, instruction)
        if not changed:
            return {
                "ok": False,
                "reason": "could not understand the revision",
                "plan": draft.to_dict(),
            }
        issues = conflicts(draft)
        if issues:
            return {
                "ok": False,
                "reason": "conflict",
                "issues": issues,
                "suggestion": "往后推 20 分钟",
                "plan": draft.to_dict(),
            }
        self._versions.setdefault(plan_id, []).append(before)
        self.repos.plans.save(draft)
        self._publish("plan.revised", draft.to_dict())
        return {"ok": True, "plan": draft.to_dict()}

    def undo(self, plan_id: str) -> PlanDraft | None:
        versions = self._versions.get(plan_id, [])
        if not versions:
            return None
        draft = versions.pop()
        self.repos.plans.save(draft)
        self._publish("plan.revised", draft.to_dict())
        return draft

    def confirm(self, plan_id: str) -> PlanDraft | None:
        draft = self.repos.plans.get(plan_id)
        if draft is None:
            return None
        self.repos.plans.update_status(plan_id, "confirmed")
        self._publish(topics.PLAN_CONFIRMED, draft.to_dict())
        return draft

    def summary(self, plan_id: str) -> dict[str, Any] | None:
        draft = self.repos.plans.get(plan_id)
        if draft is None:
            return None
        return summary_of(draft)

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("plan publish failed: %s", topic)

    def _persist_subtasks(self, draft: PlanDraft) -> None:
        for item in draft.items:
            if not item.task_id or not item.subtask_id:
                continue
            try:
                from planner.models import SubTask

                self.repos.subtasks.upsert(
                    SubTask(
                        id=item.subtask_id,
                        task_id=item.task_id,
                        title=item.title,
                        est_minutes=max(5, item.est_minutes),
                    )
                )
            except Exception:
                logger.exception("could not persist plan subtask")


def conflicts(draft: PlanDraft) -> list[str]:
    issues = []
    intervals = []
    for index, item in enumerate(draft.items):
        try:
            start = parse_hhmm(item.start)
            end = parse_hhmm(item.end)
        except Exception:
            issues.append(f"第 {index + 1} 项时间格式错误")
            continue
        if end <= start:
            issues.append(f"第 {index + 1} 项结束早于开始")
        intervals.append((start, end, index, item.title))
    intervals.sort()
    for left, right in zip(intervals, intervals[1:]):
        if right[0] < left[1]:
            issues.append(
                f"“{left[3]}”和“{right[3]}”时间重叠"
            )
    return issues


def summary_of(draft: PlanDraft) -> dict[str, Any]:
    latest = ""
    total = 0
    for item in draft.items:
        total += item.est_minutes
        latest = max(latest, item.end)
    return {
        "plan_id": draft.plan_id,
        "date": draft.date,
        "items": len(draft.items),
        "total_minutes": total,
        "last_end": latest,
        "breaks": len(draft.breaks),
        "focus_minutes": draft.focus_minutes,
        "conflicts": conflicts(draft),
    }


def _apply_instruction(draft: PlanDraft, instruction: str) -> bool:
    text = instruction.strip()
    if not text:
        return False
    shift = re.search(r"推迟\s*(\d{1,3})\s*分钟", text)
    if shift:
        minutes = int(shift.group(1))
        draft.items = [
            replace(
                item,
                start=_shift(item.start, minutes),
                end=_shift(item.end, minutes),
            )
            for item in draft.items
        ]
        return True
    shorten = re.search(r"缩短\s*(\d{1,3})\s*分钟", text)
    if shorten and draft.items:
        item = draft.items[0]
        est = max(5, item.est_minutes - int(shorten.group(1)))
        draft.items[0] = replace(
            item,
            est_minutes=est,
            end=_end(item.start, est),
        )
        return True
    move = re.search(r"把(.+?)(?:挪|移|换)到下午", text)
    if move and draft.items:
        target = move.group(1).strip("“”\"' ")
        for index, item in enumerate(draft.items):
            if target in item.title or item.title in target:
                draft.items[index] = replace(
                    item,
                    start="14:00",
                    end=_end("14:00", item.est_minutes),
                )
                return True
    duration = re.search(r"把(.+?)改成\s*(\d{1,3})\s*分钟", text)
    if duration:
        target = duration.group(1).strip("“”\"' ")
        minutes = int(duration.group(2))
        for index, item in enumerate(draft.items):
            if target in item.title or item.title in target:
                minutes = max(5, minutes)
                draft.items[index] = replace(
                    item,
                    est_minutes=minutes,
                    end=_end(item.start, minutes),
                )
                return True
    return False


def _shift(clock: str, minutes: int) -> str:
    value = datetime.combine(date.today(), parse_hhmm(clock))
    value += timedelta(minutes=minutes)
    return value.strftime("%H:%M")


def _end(start: str, minutes: int) -> str:
    return _shift(start, max(5, minutes))


def _copy(draft: PlanDraft) -> PlanDraft:
    return PlanDraft(
        plan_id=draft.plan_id,
        date=draft.date,
        items=[
            PlanItem(
                task_id=item.task_id,
                subtask_id=item.subtask_id,
                start=item.start,
                end=item.end,
                title=item.title,
                est_minutes=item.est_minutes,
            )
            for item in draft.items
        ],
        breaks=list(draft.breaks),
        notes=list(draft.notes),
        warnings=list(draft.warnings),
        mode=draft.mode,
    )
