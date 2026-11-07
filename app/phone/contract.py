"""T21 phone usage contract state machine."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from bus import topics
from data.repositories import PhoneSessionRepository
from planner.timeutil import default_tz, tz_for

logger = logging.getLogger(__name__)
DEFAULT_MINUTES = {"study": 15, "leisure": 10}


@dataclass
class PhoneContract:
    session_id: str
    purpose: str
    planned_minutes: int
    started_at: datetime
    ends_at: datetime
    extended_count: int = 0
    status: str = "running"
    reminded: bool = False

    def remaining_seconds(self, now: datetime) -> int:
        return max(0, int((self.ends_at - now).total_seconds()))

    def snapshot(self, now: datetime) -> dict[str, Any]:
        return {
            "channel": "phone",
            "title": "手机使用",
            "data": {
                "session_id": self.session_id,
                "purpose": self.purpose,
                "planned_minutes": self.planned_minutes,
                "remaining_seconds": self.remaining_seconds(now),
                "extended_count": self.extended_count,
                "status": self.status,
            },
            "hints": ["说“放回去了”结束", "学习用途可申请延长 5 分钟"],
        }


class PhoneContractService:
    def __init__(
        self,
        repo: PhoneSessionRepository,
        *,
        publisher: Any = None,
        say: Any = None,
        now_fn: Callable[[], datetime] | None = None,
        subscriber: Any = None,
    ) -> None:
        self.repo = repo
        self.publisher = publisher
        self.say = say
        self.now_fn = now_fn or (lambda: datetime.now(default_tz()))
        self.subscriber = subscriber
        self.active: PhoneContract | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._last_error = ""

    def start(self) -> "PhoneContractHealth":
        self.recover()
        if self.subscriber is not None:
            try:
                self._unsubscribe = self.subscriber.subscribe(
                    topics.PHONE_CHANGED,
                    self._on_phone,
                )
            except Exception:
                logger.exception("phone contract subscribe failed")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="flow-phone-contract",
            daemon=True,
        )
        self._thread.start()
        return PhoneContractHealth("ok", "phone contract ready")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def begin(
        self,
        purpose: str,
        minutes: int | None = None,
    ) -> PhoneContract:
        if self.active is not None:
            return self.active
        purpose = "study" if purpose == "study" else "leisure"
        value = int(minutes or DEFAULT_MINUTES[purpose])
        value = max(1, min(180, value))
        now = self.now_fn().astimezone(default_tz())
        session_id = self.repo.start(
            purpose=purpose,
            planned_minutes=value,
            started_at=now.astimezone(tz_for("UTC")).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            present_state="in_use",
        )
        self.active = PhoneContract(
            session_id=session_id,
            purpose=purpose,
            planned_minutes=value,
            started_at=now,
            ends_at=now + timedelta(minutes=value),
        )
        self._publish_state()
        self._publish(
            topics.PHONE_SESSION_STARTED,
            self._payload(),
        )
        if self.say is not None:
            self.say.say(
                f"{value} 分钟后提醒你放回手机",
                emotion="listening",
                priority="dialogue",
            )
        return self.active

    def end(self, reason: str = "manual") -> bool:
        contract = self.active
        if contract is None:
            return False
        now = self.now_fn().astimezone(default_tz())
        returned_on_time = now <= contract.ends_at
        self.repo.finish(
            contract.session_id,
            ended_at=now.astimezone(tz_for("UTC")).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            returned_on_time=returned_on_time,
        )
        self.active = None
        self._publish(
            topics.PHONE_SESSION_ENDED,
            {
                **self._payload(contract),
                "reason": reason,
                "returned_on_time": returned_on_time,
            },
        )
        self._publish(topics.CHANNEL_EXIT, {"channel": "phone"})
        if self.say is not None:
            self.say.say(
                "手机归位了，做得好",
                emotion="happy",
                priority="dialogue",
            )
        return True

    def extend(self, minutes: int = 5) -> bool:
        contract = self.active
        if contract is None:
            return False
        if contract.purpose != "study" or contract.extended_count >= 1:
            return False
        extra = max(1, min(15, int(minutes)))
        contract.ends_at += timedelta(minutes=extra)
        contract.extended_count += 1
        contract.planned_minutes += extra
        contract.reminded = False
        self._publish_state()
        self._publish(
            "phone.session.extended",
            {**self._payload(), "minutes": extra},
        )
        return True

    def tick(self, now: datetime | None = None) -> None:
        contract = self.active
        if contract is None:
            return
        moment = (now or self.now_fn()).astimezone(default_tz())
        if contract.status == "overdue":
            return
        if moment >= contract.ends_at and not contract.reminded:
            contract.reminded = True
            contract.status = "overdue"
            self._publish_state()
            self._publish(
                topics.PHONE_SESSION_OVERDUE,
                self._payload(contract),
            )
            self._publish(
                topics.REMINDER_FIRED,
                {
                    "id": f"phone-{contract.session_id}",
                    "title": "手机使用时间到了，请放回支架",
                    "kind": "phone",
                },
            )
            if self.say is not None:
                self.say.say(
                    "手机使用时间到了，请放回支架",
                    emotion="concerned",
                    priority="reminder",
                )
            return
        self._publish_state()

    def recover(self) -> None:
        open_session = self.repo.open_session()
        if open_session is None:
            return
        try:
            started = datetime.fromisoformat(
                str(open_session["started_at"]).replace("Z", "+00:00")
            ).astimezone(default_tz())
            minutes = int(open_session.get("planned_minutes") or 15)
            self.active = PhoneContract(
                session_id=str(open_session["id"]),
                purpose=str(open_session.get("purpose") or "leisure"),
                planned_minutes=minutes,
                started_at=started,
                ends_at=started + timedelta(minutes=minutes),
            )
        except Exception:
            logger.exception("phone contract recovery failed")

    def snapshot(self) -> dict[str, Any]:
        if self.active is None:
            return {"active": False, "channel": "idle"}
        return {
            "active": True,
            "channel": "phone",
            "contract": self.active.snapshot(self.now_fn()),
        }

    def health(self) -> "PhoneContractHealth":
        if self._thread is None or not self._thread.is_alive():
            return PhoneContractHealth(
                "error",
                self._last_error or "phone contract not running",
            )
        return PhoneContractHealth("ok", "phone contract running")

    def _on_phone(self, payload: dict[str, Any]) -> None:
        if payload.get("present") and self.active is not None:
            self.end("returned")

    def _loop(self) -> None:
        while not self._stop.wait(0.5):
            try:
                self.tick()
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("phone contract tick failed")

    def _publish_state(self) -> None:
        if self.active is None:
            return
        snapshot = self.active.snapshot(self.now_fn())
        self._publish(
            topics.CHANNEL_ENTER,
            {
                "channel": "phone",
                "title": "手机使用",
                "snapshot": snapshot,
                "stack": [],
            },
        )

    def _payload(
        self,
        contract: PhoneContract | None = None,
    ) -> dict[str, Any]:
        item = contract or self.active
        if item is None:
            return {}
        return {
            "id": item.session_id,
            "purpose": item.purpose,
            "planned_minutes": item.planned_minutes,
            "started_at": item.started_at.isoformat(),
            "ends_at": item.ends_at.isoformat(),
            "extended_count": item.extended_count,
            "remaining_seconds": item.remaining_seconds(self.now_fn()),
            "status": item.status,
        }

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("phone contract publish failed: %s", topic)


class PhoneContractHealth:
    def __init__(self, state: str, detail: str = "") -> None:
        self.state = state
        self.detail = detail

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}
