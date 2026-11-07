"""T15 persistent reminder scheduler."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable

from bus import topics
from data.repositories import ReminderRepository
from planner.timeutil import default_tz, tz_for
from scheduler.model import ReminderSpec, parse_reminder_text

logger = logging.getLogger(__name__)


class ReminderHealth:
    def __init__(self, state: str, detail: str = "", count: int = 0) -> None:
        self.state = state
        self.detail = detail
        self.count = count

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "detail": self.detail,
            "count": self.count,
        }


class ReminderScheduler:
    def __init__(
        self,
        repo: ReminderRepository,
        *,
        publisher: Any = None,
        say: Any = None,
        now_fn: Callable[[], datetime] | None = None,
        poll_s: float = 1.0,
        catchup_hours: float = 2.0,
    ) -> None:
        self.repo = repo
        self.publisher = publisher
        self.say = say
        self.now_fn = now_fn or (lambda: datetime.now(default_tz()))
        self.poll_s = max(0.1, poll_s)
        self.catchup_hours = catchup_hours
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._subs: list[Callable[[], None]] = []
        self._last_error = ""
        self._fired = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> ReminderHealth:
        if not self.repo:
            return ReminderHealth("disabled", "no reminder repository")
        try:
            self._catch_up()
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("reminder catchup failed")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="flow-reminders",
            daemon=True,
        )
        self._thread.start()
        self._started = True
        return ReminderHealth("ok", "reminder scheduler running")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        self._started = False
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        for unsubscribe in self._subs:
            try:
                unsubscribe()
            except Exception:
                logger.exception("reminder unsubscribe failed")
        self._subs.clear()

    def health(self) -> ReminderHealth:
        if not self.running:
            return ReminderHealth(
                "error",
                self._last_error or "reminder scheduler stopped",
            )
        return ReminderHealth("ok", "reminder scheduler running")

    def snapshot(self) -> dict[str, object]:
        return {
            "running": self.running,
            "fired": self._fired,
            "upcoming": self.upcoming(hours=24),
        }

    def create(
        self,
        spec: ReminderSpec,
        *,
        title: str = "",
    ) -> str:
        now = self.now_fn()
        next_fire = spec.next_after(now)
        reminder_id = self.repo.create(
            kind=spec.kind,
            spec=_spec_payload(spec, title),
            next_fire_at=next_fire,
        )
        if spec.kind == "event" and self.publisher is not None:
            self._subscribe_event(spec, reminder_id)
        self._publish(
            "reminder.created",
            {
                "id": reminder_id,
                "kind": spec.kind,
                "next_fire_at": next_fire,
                "template": spec.template,
            },
        )
        return reminder_id

    def create_from_text(self, text: str) -> str:
        spec = parse_reminder_text(text, now=self.now_fn())
        return self.create(spec)

    def upcoming(self, hours: int = 24) -> list[dict[str, Any]]:
        now = self.now_fn().astimezone(default_tz()).isoformat()
        return self.repo.upcoming(now, hours)

    def tick(self, now: datetime | None = None) -> list[dict[str, Any]]:
        moment = (now or self.now_fn()).astimezone(default_tz())
        now_utc = moment.astimezone(tz_for("UTC")).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        fired: list[dict[str, Any]] = []
        for row in self.repo.due(now_utc):
            spec = _row_spec(row)
            if spec is None:
                continue
            if self._fire(row, spec, moment):
                fired.append(row.get("last_fired_at") and row or row)
        return fired

    def _fire(
        self,
        row: dict[str, Any],
        spec: ReminderSpec,
        now: datetime,
    ) -> bool:
        reminder_id = str(row["id"])
        template = str(spec.template)
        text = _render(template)
        payload = {
            "id": reminder_id,
            "title": text,
            "kind": spec.kind,
            "payload": {"text": text, "allow_quiet": spec.allow_quiet},
        }
        self._publish(topics.REMINDER_FIRED, payload)
        if self.say is not None:
            try:
                self.say.say(
                    text,
                    emotion="concerned",
                    priority="reminder",
                    now=now,
                )
            except Exception:
                logger.exception("reminder speech failed")
        next_fire = spec.next_after(now, last_fired=now)
        self.repo.mark_fired(
            reminder_id,
            next_fire_at=next_fire,
            fired_at=now.astimezone(tz_for("UTC")).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
        )
        self._fired += 1
        return True

    def _catch_up(self) -> None:
        now = self.now_fn().astimezone(default_tz())
        cutoff = now - timedelta(hours=self.catchup_hours)
        missed = []
        for row in self.repo.list_all(enabled_only=True):
            next_fire = row.get("next_fire_at")
            if not next_fire:
                continue
            parsed = datetime.fromisoformat(
                str(next_fire).replace("Z", "+00:00")
            ).astimezone(default_tz())
            if parsed < cutoff:
                missed.append(row)
            elif parsed <= now:
                self.tick(now)
        if missed:
            count = len(missed)
            for row in missed:
                spec = _row_spec(row)
                if spec is not None:
                    next_fire = spec.next_after(now, last_fired=now)
                    self.repo.mark_fired(
                        str(row["id"]),
                        next_fire_at=next_fire,
                        fired_at=now.isoformat(),
                    )
            text = f"这段时间有 {count} 条提醒，已经帮你合并了"
            self._publish(
                topics.REMINDER_FIRED,
                {"id": "catchup", "title": text, "kind": "catchup"},
            )
            if self.say is not None:
                self.say.say(text, emotion="concerned", priority="reminder")

    def _subscribe_event(
        self,
        spec: ReminderSpec,
        reminder_id: str,
    ) -> None:
        if self.publisher is None:
            return
        if not hasattr(self.publisher, "subscribe"):
            return

        def handler(_payload: dict[str, Any]) -> None:
            row = self.repo.get(reminder_id)
            if row and row.get("enabled"):
                self._fire(row, spec, self.now_fn())
        try:
            self._subs.append(self.publisher.subscribe(spec.on, handler))
        except Exception:
            logger.exception("reminder event subscribe failed")

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_s):
            try:
                self.tick()
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("reminder tick failed")

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("reminder publish failed: %s", topic)


def _spec_payload(spec: ReminderSpec, title: str) -> dict[str, Any]:
    payload = spec.to_dict()
    if title:
        payload["title"] = title
    return payload


def _row_spec(row: dict[str, Any]) -> ReminderSpec | None:
    import json

    try:
        raw = json.loads(row.get("spec_json") or "{}")
        return ReminderSpec.from_dict(raw)
    except Exception:
        logger.exception("invalid reminder spec: %s", row.get("id"))
        return None


def _render(template: str) -> str:
    try:
        return template.format(brief="", weather="")
    except (KeyError, ValueError):
        return template
