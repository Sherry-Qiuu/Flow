"""Reminder channel."""

from __future__ import annotations

from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class ReminderChannel(BaseChannel):
    key = "reminder"
    title = "提醒"

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del args
        self.ctx = ctx
        repos = ctx.repos
        due = repos.reminders.due() if repos is not None else []
        return self._finish(
            {"due": due, "count": len(due)},
            ["说“打开任务清单”查看任务", "提醒到点会自动出现"],
        )

    def handle(self, intent: Intent) -> list[Action]:
        if intent.name == "back":
            return [Action("back", {})]
        return []
