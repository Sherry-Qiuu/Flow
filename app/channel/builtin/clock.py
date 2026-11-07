"""Clock channel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class ClockChannel(BaseChannel):
    key = "clock"
    title = "时钟"

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del args
        self.ctx = ctx
        now = ctx.now()
        return self._finish(
            {
                "time": now.strftime("%H:%M"),
                "date": now.strftime("%Y-%m-%d"),
                "weekday": "一二三四五六日"[now.weekday()],
            },
            ["说“任务清单”查看待办", "说“专注计时”开始专注"],
        )

    def tick(self, now: datetime) -> list[Action]:
        data = {
            "time": now.strftime("%H:%M"),
            "date": now.strftime("%Y-%m-%d"),
            "weekday": "一二三四五六日"[now.weekday()],
        }
        self._finish(data, self.snapshot()["hints"])
        return []

    def handle(self, intent: Intent) -> list[Action]:
        del intent
        return []
