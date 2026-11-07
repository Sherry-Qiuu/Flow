"""T28 demo reset and scripted fallback."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from data.locking import get_connection_lock
from data.repositories import Repositories
from planner.models import Task

logger = logging.getLogger(__name__)

DEMO_TASKS = (
    ("demo_paper", "写 3000 字课程论文", 90),
    ("demo_physics", "整理物理实验报告", 45),
    ("demo_words", "背 30 个单词", 20),
)


class DemoService:
    def __init__(
        self,
        repos: Repositories,
        *,
        connection=None,
        marker: str | Path = "data/demo_state.json",
    ) -> None:
        self.repos = repos
        self.connection = connection
        self.marker = Path(marker)
        self._lock = (
            get_connection_lock(connection)
            if connection is not None
            else None
        )

    def reset(self) -> dict[str, Any]:
        if self.connection is not None:
            with self._lock:
                for table in (
                    "focus_sessions",
                    "phone_sessions",
                    "reminders",
                    "distractions",
                    "reward_events",
                    "device_events",
                    "metrics_daily",
                    "plans",
                    "tasks",
                ):
                    self.connection.execute(
                        f"DELETE FROM {table} WHERE user_id = ?",
                        (self.repos.user_id,),
                    )
                self.connection.commit()
        created = []
        for task_id, title, minutes in DEMO_TASKS:
            task = Task(
                id=task_id,
                title=title,
                est_minutes=minutes,
                source="demo",
            )
            self.repos.tasks.upsert(task)
            created.append(task.to_dict())
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        self.marker.write_text(
            json.dumps(
                {"reset_at": datetime.now().isoformat(timespec="seconds")}
            ),
            encoding="utf-8",
        )
        return {"ok": True, "tasks": created}

    def scripted_response(self, text: str) -> str:
        if "任务" in text:
            return "我已经准备好了三条演示任务，随时可以开始。"
        if "计划" in text:
            return "我会先列一个三步计划，再和你确认。"
        if "手机" in text:
            return "手机放回支架后，计时会自动结束。"
        return "我在，慢慢说。"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Flow demo reset")
    parser.add_argument("--db", default="data/flow.db")
    parser.add_argument("--user", default="u_default")
    args = parser.parse_args()
    from data.database import FlowDatabase
    from data.repositories import repositories

    database = FlowDatabase(args.db)
    if not database.start().ok:
        print("database unavailable")
        return 1
    ensure_user(database.connection, args.user, "Demo")
    result = DemoService(
        repositories(database.connection, args.user),
        connection=database.connection,
        marker=Path(args.db).parent / "demo_state.json",
    ).reset()
    print(json.dumps(result, ensure_ascii=False))
    database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def ensure_user(connection, user_id: str, name: str) -> None:
    from data.database import ensure_user as _ensure

    _ensure(connection, user_id, name)
