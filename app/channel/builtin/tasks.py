"""Tasks channel."""

from __future__ import annotations

from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class TasksChannel(BaseChannel):
    key = "tasks"
    title = "任务清单"

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del args
        self.ctx = ctx
        repos = ctx.repos
        tasks = repos.tasks.list() if repos is not None else []
        items = [
            {
                "id": task.id,
                "title": task.title,
                "status": "done" if task.completed else "pending",
                "est_minutes": task.est_minutes,
                "priority": task.priority,
            }
            for task in tasks
        ]
        return self._finish(
            {"items": items, "count": len(items)},
            ["说“完成第一条”标记完成", "说“打开专注计时”开始做"],
        )

    def handle(self, intent: Intent) -> list[Action]:
        repos = self._repos()
        if intent.name in {"complete_task", "done"} and repos is not None:
            task_id = intent.args.get("task_id")
            if not task_id:
                task_id = self._first_pending()
            if task_id and repos.tasks.update_status(task_id, "done"):
                return [
                    Action("task.updated", {"task_id": task_id}),
                    Action("speak", {"text": "完成了，做得不错"}),
                ]
            return [Action("speak", {"text": "没有找到可以完成的任务"})]
        if intent.name == "back":
            return [Action("back", {})]
        return []

    def _first_pending(self) -> str | None:
        data = self.snapshot().get("data", {})
        for item in data.get("items", []):
            if item.get("status") != "done":
                return item.get("id")
        return None
