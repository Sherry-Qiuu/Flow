"""Plan channel."""

from __future__ import annotations

from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class PlanChannel(BaseChannel):
    key = "plan"
    title = "计划表"

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del args
        self.ctx = ctx
        repos = ctx.repos
        rows = repos.plans.list() if repos is not None else []
        plans = [
            {
                "id": row["id"],
                "date": row["plan_date"],
                "status": row["status"],
                "version": row["version"],
            }
            for row in rows
        ]
        return self._finish(
            {"plans": plans, "count": len(plans)},
            ["说“打开任务清单”查看任务", "说“开始专注”进入计时"],
        )

    def handle(self, intent: Intent) -> list[Action]:
        if intent.name == "back":
            return [Action("back", {})]
        return []
