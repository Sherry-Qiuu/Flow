"""T14 focus session with single-step advance and recovery."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any

from bus import topics
from data.repositories import Repositories
from planner.timeutil import tz_for

logger = logging.getLogger(__name__)
TZ = tz_for("Asia/Shanghai")


@dataclass
class FocusState:
    plan_id: str = ""
    item_id: str = ""
    title: str = ""
    detail: str = "只做眼前这一步"
    index: int = 0
    total: int = 0
    total_s: int = 0
    remaining_s: int = 0
    status: str = "idle"
    stuck_count: int = 0
    overrun_notified: bool = False
    saved_at: str = ""
    session_id: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.plan_id,
            "subtask_id": self.item_id,
            "title": self.title,
            "detail": self.detail,
            "remaining_ms": max(0, self.remaining_s) * 1000,
            "total_ms": max(1, self.total_s) * 1000,
            "minutes": max(1, self.total_s // 60),
            "index": self.index,
            "total": self.total,
            "status": self.status,
            "stuck_count": self.stuck_count,
            "remaining_seconds": max(0, self.remaining_s),
        }


class FocusStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, state: FocusState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(state), ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> FocusState | None:
        if not self.path.is_file():
            return None
        try:
            return FocusState(**json.loads(self.path.read_text("utf-8")))
        except Exception:
            logger.exception("focus state load failed")
            return None


class FocusService:
    def __init__(
        self,
        repos: Repositories,
        *,
        publisher: Any = None,
        say: Any = None,
        store_path: str | Path = "data/focus_state.json",
        now_fn=None,
        clock=time.monotonic,
    ) -> None:
        self.repos = repos
        self.publisher = publisher
        self.say = say
        self.store = FocusStateStore(store_path)
        self.now_fn = now_fn or (lambda: datetime.now(TZ))
        self.clock = clock
        self.state = FocusState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_tick = clock()
        self._last_persist = clock()

    def start(self) -> "FocusHealth":
        recovered = self.store.load()
        if recovered is not None and recovered.status in {
            "running",
            "paused",
        }:
            self.state = recovered
            if recovered.saved_at:
                try:
                    saved = datetime.fromisoformat(recovered.saved_at)
                    elapsed = max(
                        0,
                        int(
                            (
                                self.now_fn().astimezone(TZ)
                                - saved.astimezone(TZ)
                            ).total_seconds()
                        ),
                    )
                    if recovered.status == "running":
                        self.state.remaining_s = max(
                            0, recovered.remaining_s - elapsed
                        )
                except ValueError:
                    pass
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="flow-focus",
            daemon=True,
        )
        self._thread.start()
        return FocusHealth("ok", "focus service running")

    def stop(self) -> None:
        self._stop.set()
        self._persist()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def begin(self, plan_id: str) -> dict[str, Any]:
        plan = self.repos.plans.get(plan_id)
        if plan is None:
            return {"ok": False, "reason": "plan not found"}
        rows = self.repos.plan_items.list(plan_id)
        pending = [
            (index, row)
            for index, row in enumerate(rows)
            if row["status"] in {"pending", "paused"}
        ]
        if not pending:
            return {"ok": False, "reason": "plan has no pending item"}
        index, current = pending[0]
        self.state = FocusState(
            plan_id=plan_id,
            item_id=str(current["id"]),
            title=str(current["title"]),
            index=index,
            total=len(rows),
            total_s=max(60, int(current["est_minutes"]) * 60),
            remaining_s=max(60, int(current["est_minutes"]) * 60),
            status="running",
            saved_at=self.now_fn().astimezone(TZ).isoformat(),
        )
        self.repos.plan_items.update_status(self.state.item_id, "running")
        self.state.session_id = self.repos.focus_sessions.start(
            plan_item_id=self.state.item_id,
        )
        self._publish_state()
        self._persist()
        self._say(f"先做这一步：{self.state.title}")
        return {"ok": True, "state": self.state.snapshot()}

    def control(
        self,
        action: str,
        minutes: int | None = None,
    ) -> dict[str, Any]:
        action = str(action or "").lower()
        if self.state.status == "idle":
            return {"ok": False, "reason": "no active focus"}
        if action in {"start", "resume"}:
            self.state.status = "running"
        elif action == "pause":
            self.state.status = "paused"
        elif action == "finish":
            return self._advance("done")
        elif action == "skip":
            return self._advance("skipped")
        elif action == "stuck":
            return self._stuck()
        elif action == "extend":
            extra = max(1, min(30, int(minutes or 10))) * 60
            self.state.remaining_s += extra
            self.state.total_s += extra
            self.state.overrun_notified = False
        else:
            return {"ok": False, "reason": "unknown action"}
        self._publish_state()
        self._persist()
        return {"ok": True, "state": self.state.snapshot()}

    def snapshot(self) -> dict[str, Any]:
        return self.state.snapshot()

    def switch_user(self, repos: Repositories, store_path: str | Path) -> None:
        self._persist()
        self.repos = repos
        self.store = FocusStateStore(store_path)
        recovered = self.store.load()
        self.state = recovered or FocusState()

    def health(self) -> "FocusHealth":
        if self._thread is None or not self._thread.is_alive():
            return FocusHealth("error", "focus service not running")
        return FocusHealth("ok", "focus service running")

    def replan(self, reason: str = "delay") -> dict[str, Any]:
        from dataclasses import replace

        plan = self.repos.plans.get(self.state.plan_id)
        if plan is None or not plan.items:
            return {"ok": False, "reason": "no plan"}
        delay = 20 if reason == "delay" else 0
        plan.items = [
            replace(
                item,
                start=_shift(item.start, delay),
                end=_shift(item.end, delay),
            )
            if index > self.state.index
            else item
            for index, item in enumerate(plan.items)
        ]
        self.repos.plans.save(plan)
        self._publish("plan.replanned", {"reason": reason})
        return {"ok": True, "plan": plan.to_dict()}

    def _advance(self, status: str) -> dict[str, Any]:
        self.repos.plan_items.update_status(self.state.item_id, status)
        if self.state.session_id is not None:
            self.repos.focus_sessions.finish(self.state.session_id)
        self._publish(
            "plan.item.advanced",
            {"from_id": self.state.item_id, "status": status},
        )
        self._publish(
            topics.REWARD_EVENT,
            {
                "kind": "task_done" if status == "done" else "step_done",
                "title": self.state.title,
            },
        )
        rows = self.repos.plan_items.list(self.state.plan_id)
        pending = [
            (index, row)
            for index, row in enumerate(rows)
            if row["status"] in {"pending", "paused"}
        ]
        if not pending:
            self.state.status = "done"
            self._publish("plan.completed", {"plan_id": self.state.plan_id})
            self._persist()
            return {"ok": True, "done": True, "state": self.state.snapshot()}
        index, current = pending[0]
        self.state.item_id = str(current["id"])
        self.state.title = str(current["title"])
        self.state.index = index
        self.state.total_s = max(60, int(current["est_minutes"]) * 60)
        self.state.remaining_s = self.state.total_s
        self.state.status = "running"
        self.state.stuck_count = 0
        self.state.overrun_notified = False
        self.state.session_id = self.repos.focus_sessions.start(
            plan_item_id=self.state.item_id,
        )
        self._publish_state()
        self._persist()
        return {"ok": True, "state": self.state.snapshot()}

    def _stuck(self) -> dict[str, Any]:
        self.state.stuck_count += 1
        if self.state.stuck_count >= 2:
            self.state.title = f"先做 5 分钟：{self.state.title}"
            self.state.total_s = min(self.state.total_s, 300)
            self.state.remaining_s = min(self.state.remaining_s, 300)
            self.state.status = "running"
            self.state.stuck_count = 0
            self._publish("focus.split", {"title": self.state.title})
            self._say("把这一步缩小到 5 分钟，先动起来")
        self._publish_state()
        self._persist()
        return {"ok": True, "state": self.state.snapshot()}

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            now = self.clock()
            delta = max(0.0, now - self._last_tick)
            self._last_tick = now
            if self.state.status != "running":
                continue
            self.state.remaining_s = max(
                0, self.state.remaining_s - int(delta)
            )
            if self.state.remaining_s == 0 and not self.state.overrun_notified:
                self.state.overrun_notified = True
                self._publish(
                    "focus.overdue",
                    {"title": self.state.title, "plan_id": self.state.plan_id},
                )
                self._say(
                    "这一步超出预估了，要延长、跳过还是换个简单的？"
                )
            self._publish_state()
            if now - self._last_persist > 5:
                self._persist()

    def _say(self, text: str) -> None:
        if self.say is None:
            return
        try:
            self.say.say(
                text,
                emotion="concerned",
                priority="dialogue",
            )
        except Exception:
            logger.exception("focus speech failed")

    def _publish_state(self) -> None:
        self._publish(topics.FOCUS_STATE, self.state.snapshot())

    def _persist(self) -> None:
        self.state.saved_at = self.now_fn().astimezone(TZ).isoformat()
        try:
            self.store.save(self.state)
        except Exception:
            logger.exception("focus persist failed")
        self._last_persist = self.clock()

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("focus publish failed: %s", topic)


class FocusHealth:
    def __init__(self, state: str, detail: str = "") -> None:
        self.state = state
        self.detail = detail

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _shift(clock: str, minutes: int) -> str:
    value = datetime.combine(date.today(), _parse_hhmm(clock))
    value += timedelta(minutes=minutes)
    return value.strftime("%H:%M")


def _parse_hhmm(value: str) -> clock_time:
    hour, _, minute = value.partition(":")
    return clock_time(int(hour), int(minute or 0))
