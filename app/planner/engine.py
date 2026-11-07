"""Public rule-based planning engine.

This is the guaranteed offline path for T12. An LLM adapter can wrap
:class:`RuleEngine` and call these methods whenever generation fails,
times out or returns invalid JSON.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date

from planner.estimator import HistoryProvider, estimate_minutes
from planner.models import PlanDraft, Prefs, SubTask, Task, make_plan_id
from planner.rules import decompose_task, max_decomposable_minutes
from planner.scheduler import build_plan
from planner.timeutil import default_tz_name
from planner.validator import ValidationResult, validate_plan

logger = logging.getLogger(__name__)


class RuleEngine:
    """Deterministic decomposition and daily packing."""

    def __init__(
        self,
        prefs: Prefs | None = None,
        history: HistoryProvider | None = None,
        *,
        strict: bool = False,
    ) -> None:
        # Windows are placed in the configured display zone, not a frozen
        # constant, so FLOW_TIMEZONE also moves the plan's evening block.
        self.prefs = prefs or Prefs(timezone=default_tz_name())
        self.history = history
        self.strict = strict
        self.last_validation: ValidationResult | None = None

    def decompose(
        self,
        task: Task,
        prefs: Prefs | None = None,
    ) -> list[SubTask]:
        return decompose_task(task, prefs or self.prefs, self.history)

    def plan(
        self,
        plan_date: date,
        tasks: list[Task],
        prefs: Prefs | None = None,
    ) -> PlanDraft:
        """Always return a draft, even when no time is available."""
        active_prefs = prefs or self.prefs
        prepared: list[Task] = []
        capped: list[tuple[Task, int]] = []
        for task in tasks:
            if task.completed or task.subtasks:
                prepared.append(task)
                continue
            estimate = estimate_minutes(task, self.history)
            capped_at = max_decomposable_minutes(active_prefs)
            if estimate > capped_at:
                capped.append((task, estimate))
            prepared.append(
                replace(task, subtasks=self.decompose(task, active_prefs))
            )

        try:
            draft = build_plan(
                plan_date,
                prepared,
                active_prefs,
                mode="rule",
            )
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("rule planner failed")
            draft = PlanDraft(
                plan_id=make_plan_id(plan_date),
                date=plan_date.isoformat(),
                warnings=[f"规划失败，已返回空计划：{exc}"],
                mode="rule",
            )
        for task, estimate in capped:
            draft.warnings.append(
                f"《{task.title}》预计 {estimate} 分钟，超过单日拆解上限，"
                "已压缩为可执行的前几步"
            )

        self.last_validation = validate_plan(
            draft,
            prepared,
            active_prefs,
            plan_date=plan_date,
        )
        if not self.last_validation.ok:
            for issue in self.last_validation.errors:
                draft.warnings.append(f"内部校验未通过：{issue.message}")
            if self.strict:
                self.last_validation.raise_for_errors()
        return draft

    def validate(
        self,
        plan: PlanDraft,
        tasks: list[Task],
        prefs: Prefs | None = None,
    ) -> ValidationResult:
        return validate_plan(
            plan,
            tasks,
            prefs or self.prefs,
            plan_date=date.fromisoformat(plan.date),
        )


def decompose(
    task: Task,
    prefs: Prefs | None = None,
    history: HistoryProvider | None = None,
) -> list[SubTask]:
    """Contract helper: ``decompose(task, prefs) -> list[SubTask]``."""
    return RuleEngine(prefs, history).decompose(task)


def plan(
    plan_date: date,
    tasks: list[Task],
    prefs: Prefs | None = None,
    history: HistoryProvider | None = None,
) -> PlanDraft:
    """Contract helper: ``plan(date, tasks, prefs) -> PlanDraft``."""
    return RuleEngine(prefs, history).plan(plan_date, tasks)
