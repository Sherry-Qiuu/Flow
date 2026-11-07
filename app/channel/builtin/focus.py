"""Focus timer channel: a thin view over ``focus.service.FocusService``.

The channel no longer keeps its own counter. It used to publish
``focus.state`` with ``remaining_seconds`` while FocusService published the
same topic with ``remaining_ms``/``title``; the screen received both once a
second and flickered between a real plan step and a fake one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class FocusChannel(BaseChannel):
    key = "focus"
    title = "专注计时"

    def __init__(self) -> None:
        super().__init__()
        self._minutes = 25
        self._remaining_s = 25 * 60
        self._running = False
        self._session_id: str | None = None

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ctx = ctx
        self._minutes = _positive_int((args or {}).get("minutes"), 25)
        focus = _focus(ctx)
        if focus is not None:
            state = focus.snapshot()
            if state.get("status") in {"running", "paused"}:
                return self._finish(_from_state(state), self._hints(state))
        self._remaining_s = min(max(self._minutes, 1), 180) * 60
        self._running = False
        self._session_id = None
        return self._finish(
            self._data(),
            ["说“开始”启动计时", "说“暂停”或“结束”"],
        )

    def exit(self) -> None:
        # Leaving the channel must not silently kill a running session; the
        # focus service owns the timer now.
        self._running = False
        super().exit()

    def handle(self, intent: Intent) -> list[Action]:
        name = intent.name
        focus = _focus(self.ctx)
        if focus is not None:
            return self._delegate(focus, name)
        return self._local(name)

    def tick(self, now: datetime) -> list[Action]:
        del now
        if _focus(self.ctx) is not None:
            # FocusService publishes focus.state at 1 Hz.
            return []
        return self._local_tick()

    def snapshot(self) -> dict[str, Any]:
        hints = self._snapshot.get("hints", [])
        focus = _focus(self.ctx)
        if focus is not None:
            state = focus.snapshot()
            if state.get("status") in {"running", "paused"}:
                return self._finish(_from_state(state), self._hints(state))
        return self._finish(self._data(), hints)

    def _delegate(self, focus: Any, name: str) -> list[Action]:
        state = focus.snapshot()
        active = state.get("status") in {"running", "paused"}
        if name in {"start", "resume", "focus_start"}:
            if active:
                focus.control("resume")
            else:
                focus.begin_timer(self._minutes)
            return [Action("speak", {"text": "开始专注，我在"})]
        if name in {"pause", "focus_pause"}:
            if active:
                focus.control("pause")
            return [Action("speak", {"text": "已暂停"})]
        if name in {"finish", "stop", "focus_finish"}:
            if active:
                focus.control("finish")
            return [Action("speak", {"text": "这一步完成，休息一下"})]
        if name == "back":
            return [Action("back", {})]
        return []

    def _local(self, name: str) -> list[Action]:
        """Fallback used when no FocusService is wired (unit tests)."""
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

    def _local_tick(self) -> list[Action]:
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

    def _data(self) -> dict[str, Any]:
        minutes = (self._remaining_s + 59) // 60
        return {
            "remaining_seconds": self._remaining_s,
            "remaining_minutes": max(1, minutes),
            "running": self._running,
            "session_id": self._session_id,
            "status": "running" if self._running else "idle",
        }

    def _hints(self, state: dict[str, Any]) -> list[str]:
        if state.get("status") == "paused":
            return ["说“继续”恢复计时", "说“结束”结束这一步"]
        return ["说“暂停”或“结束”", "说“返回”回到主页"]

    def _finish_session(self) -> None:
        repos = self._repos()
        if repos is not None and self._session_id is not None:
            repos.focus_sessions.finish(self._session_id)
        self._session_id = None


def _focus(ctx: ChannelContext | None) -> Any:
    return getattr(ctx, "focus", None) if ctx is not None else None


def _from_state(state: dict[str, Any]) -> dict[str, Any]:
    remaining = int(state.get("remaining_seconds") or 0)
    return {
        "remaining_seconds": remaining,
        "remaining_minutes": max(1, (remaining + 59) // 60),
        "running": state.get("status") == "running",
        "status": state.get("status", "idle"),
        "title": state.get("title", ""),
        "session_id": state.get("session_id"),
    }


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
