"""Demo: rule-based decomposition and plan for a messy evening.

Run from the ``app`` directory::

    python -m planner
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time

from planner import Prefs, RuleEngine, Task, TimeWindow

SAMPLE_TASKS = (
    Task(
        id="t1",
        title="写 3000 字论文",
        deadline=datetime(2026, 11, 8, 23, 0),
        priority=1,
    ),
    Task(id="t2", title="读完第 3 章教材", priority=2),
    Task(id="t3", title="背 50 个单词", priority=3),
    Task(id="t4", title="准备小组讨论", priority=3),
    Task(id="t5", title="整理实验数据", priority=2),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flow rule planner demo")
    parser.add_argument(
        "--date",
        default="2026-11-08",
        help="plan date (YYYY-MM-DD)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    day = date.fromisoformat(args.date)
    prefs = Prefs(
        default_windows=(TimeWindow(time(19, 0), time(22, 0)),),
    )
    engine = RuleEngine(prefs)
    essay = engine.decompose(SAMPLE_TASKS[0])
    draft = engine.plan(day, list(SAMPLE_TASKS))

    if args.json:
        print(
            json.dumps(
                {
                    "decomposition": [
                        subtask.to_dict() for subtask in essay
                    ],
                    "plan": draft.to_dict(),
                    "validation": (
                        engine.last_validation.to_dict()
                        if engine.last_validation
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print("拆解「写 3000 字论文」")
    for subtask in essay:
        print(
            f"  {subtask.order}. {subtask.title} "
            f"({subtask.est_minutes} min)"
        )
    print()
    print(f"计划 {draft.date}（{draft.mode}）")
    for item in draft.items:
        print(
            f"  {item.start}-{item.end}  {item.title}  "
            f"({item.est_minutes} min)"
        )
    for entry in draft.breaks:
        print(f"  {entry.start}  休息 {entry.minutes} 分钟")
    print()
    print(f"专注 {draft.focus_minutes} 分钟，"
          f"休息 {draft.break_minutes} 分钟")
    for note in draft.notes:
        print(f"  - {note.text}")
    for warning in draft.warnings:
        print(f"  ! {warning}")
    if engine.last_validation is not None:
        status = "通过" if engine.last_validation.ok else "未通过"
        print(f"校验：{status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
