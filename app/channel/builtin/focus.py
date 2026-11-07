"""Focus timer channel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class FocusChannel(BaseChannel):
    key = "focus"
    title = "专注计时"

    def __init__(self) -> None:
        super().__init__()
        self._remaining_s = 25 * 60
        self._running = False
        self._session_id: str | None = None

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ctx = ctx
        minutes = _positive_int((args or {}).get("minutes"), 25)
        self._remaining_s = min(max(minutes, 1), 180) * 60
        self._running = False
        self._session_id = None
        return self._finish(
            self._data(),
            ["说“开始”启动计时", "说“暂停”或“结束”"],
        )

    def exit(self) -> None:
        if self._running:
            self._finish_session()
        self._running = False
        super().exit()

    def handle(self, intent: Intent) -> list[Action]:
        name = intent.name
        if name in {"start", "resume", "focus_start"}:
            if not self._running:
                self._running = True
                if self._session_id is None and self._repos() is not None:
                    self._session_id = self._repos().focus_sessions.start(
                        started_at=self.ctx.now().isoformat()
                        if self.ctx
                        else None
                    )
            return [
                Action("focus.state", self._data()),
                Action("speak", {"text": "开始专注，我在"}),
            ]
        if name in {"pause", "focus_pause"}:
            self._running = False
            return [
                Action("focus.state", self._data()),
                Action("speak", {"text": "已暂停"}),
            ]
        if name in {"finish", "stop", "focus_finish"}:
            self._finish_session()
            self._running = False
            return [
                Action("focus.state", self._data()),
                Action("speak", {"text": "这一步完成，休息一下"}),
            ]
        if name == "back":
            return [Action("back", {})]
        return []

    def tick(self, now: datetime) -> list[Action]:
        del now
        if not self._running:
            return []
        self._remaining_s = max(0, self._remaining_s - 1)
        if self._remaining_s == 0:
            self._finish_session()
            self._running = False
            return [
                Action("focus.state", self._data()),
                Action("speak", {"text": "时间到，休息一下"}),
            ]
        return [Action("focus.state", self._data())]

    def snapshot(self) -> dict[str, Any]:
        hints = self._snapshot.get("hints", [])
        return self._finish(self._data(), hints)

    def _data(self) -> dict[str, Any]:
        minutes = max(1, self._remaining_s // 60)
        return {
            "remaining_seconds": self._remaining_s,
            "remaining_minutes": minutes,
            "running": self._running,
            "session_id": self._session_id,
        }

    def _finish_session(self) -> None:
        repos = self._repos()
        if repos is not None and self._session_id is not None:
            repos.focus_sessions.finish(self._session_id)
        self._session_id = None


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
