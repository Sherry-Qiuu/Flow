"""Rule-based task decomposition and daily planning (T12)."""

from planner.engine import RuleEngine, decompose, plan
from planner.estimator import HistoryProvider, estimate_minutes, infer_category
from planner.models import (
    Break,
    Category,
    PlanDraft,
    PlanItem,
    PlanNote,
    Prefs,
    SubTask,
    Task,
    TimeWindow,
)
from planner.validator import (
    PlanValidationError,
    ValidationIssue,
    ValidationResult,
    is_verb_first,
    validate_plan,
)

__all__ = [
    "Break",
    "Category",
    "HistoryProvider",
    "PlanDraft",
    "PlanItem",
    "PlanNote",
    "PlanValidationError",
    "Prefs",
    "RuleEngine",
    "SubTask",
    "Task",
    "TimeWindow",
    "ValidationIssue",
    "ValidationResult",
    "decompose",
    "estimate_minutes",
    "infer_category",
    "is_verb_first",
    "plan",
    "validate_plan",
]
