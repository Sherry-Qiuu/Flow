"""Rule-based decomposition used when the LLM is unavailable."""

from __future__ import annotations

import math

from planner.estimator import HistoryProvider, estimate_minutes, infer_category
from planner.models import Prefs, SubTask, Task
from planner.templates import TEMPLATES


def max_decomposable_minutes(prefs: Prefs) -> int:
    """Largest duration that fits the first-step and per-step caps."""
    return prefs.max_first_step_minutes + prefs.max_step_minutes * (
        prefs.max_steps - 1
    )


def decompose_task(
    task: Task,
    prefs: Prefs | None = None,
    history: HistoryProvider | None = None,
) -> list[SubTask]:
    """Split one task into 3-7 verb-first, 15-45 minute steps."""
    prefs = prefs or Prefs()
    if task.subtasks:
        return list(task.subtasks)

    category = infer_category(task)
    raw_estimate = estimate_minutes(task, history)
    cap = max_decomposable_minutes(prefs)
    floor = prefs.min_steps * prefs.min_step_minutes
    total = max(floor, min(cap, raw_estimate))
    count = choose_step_count(total, prefs)
    templates = TEMPLATES[category]
    indices = select_indices(len(templates), count)
    durations = allocate_durations(total, count, prefs)

    short_title = task.title
    if len(short_title) > 18:
        short_title = short_title[:17] + "…"

    subtasks: list[SubTask] = []
    for position, (template_index, minutes) in enumerate(
        zip(indices, durations),
        start=1,
    ):
        template = templates[template_index]
        title = template.title.format(task=short_title)
        subtasks.append(
            SubTask(
                id=f"{task.id}_s{position}",
                task_id=task.id,
                title=title,
                est_minutes=minutes,
                completion_criteria=template.criteria,
                order=position,
                difficulty=template.difficulty,
                source="rule",
            )
        )
    return subtasks


def choose_step_count(total: int, prefs: Prefs) -> int:
    """Pick a step count that can honor every duration cap."""
    lower = max(
        prefs.min_steps,
        math.ceil(total / float(prefs.max_step_minutes)),
    )
    upper = min(
        prefs.max_steps,
        total // prefs.min_step_minutes,
    )
    if upper < lower:
        return max(prefs.min_steps, min(prefs.max_steps, lower))
    preferred = int(round(total / 25.0))
    return max(lower, min(upper, preferred))


def select_indices(template_size: int, count: int) -> list[int]:
    """Spread selected phases from the first to the last template step."""
    if count >= template_size:
        return list(range(template_size))
    if count <= 1:
        return [0]
    step = (template_size - 1) / float(count - 1)
    indices = [int(round(index * step)) for index in range(count)]
    return sorted(set(indices))


def allocate_durations(total: int, count: int, prefs: Prefs) -> list[int]:
    """Split ``total`` into integer minutes within per-step limits.

    The first step gets a tighter cap so the user can start within
    20 minutes. Leftover minutes are shared evenly.
    """
    minimum = prefs.min_step_minutes
    caps = [prefs.max_first_step_minutes] + [
        prefs.max_step_minutes
    ] * (count - 1)
    if total < minimum * count:
        raise ValueError("total is too small for the requested step count")
    if total > sum(caps):
        raise ValueError("total is too large for the requested step count")

    targets = [float(minimum)] * count
    remaining = float(total - minimum * count)
    while remaining > 1e-6:
        flexible = [
            index
            for index in range(count)
            if targets[index] < caps[index] - 1e-9
        ]
        if not flexible:
            break
        share = remaining / len(flexible)
        moved = 0.0
        for index in flexible:
            added = min(share, caps[index] - targets[index])
            targets[index] += added
            moved += added
        if moved <= 1e-9:
            break
        remaining -= moved

    values = [int(round(value)) for value in targets]
    difference = total - sum(values)
    while difference != 0:
        if difference > 0:
            candidates = [
                index
                for index in range(count)
                if values[index] < caps[index]
            ]
            if not candidates:
                break
            for index in candidates:
                if difference == 0:
                    break
                values[index] += 1
                difference -= 1
        else:
            candidates = [
                index
                for index in reversed(range(count))
                if values[index] > minimum
            ]
            if not candidates:
                break
            for index in candidates:
                if difference == 0:
                    break
                values[index] -= 1
                difference += 1
    if sum(values) != total:
        raise ValueError("duration allocation did not converge")
    if any(value < minimum for value in values):
        raise ValueError("duration allocation produced a short step")
    if any(
        value > caps[index] for index, value in enumerate(values)
    ):
        raise ValueError("duration allocation produced a long step")
    return values
