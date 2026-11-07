"""T20 phone session service: poll HAL, debounce, persist, expose health."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from bus import topics
from data.repositories import PhoneSessionRepository
from hal.contracts import PhoneStand, PhoneState
from phone.session_store import PhoneSessionStore, PhoneSnapshot

logger = logging.getLogger(__name__)


class PhoneSessionService:
    def __init__(
        self,
        phone_stand: PhoneStand | None,
        repo: PhoneSessionRepository,
        *,
        poll_ms: int = 100,
        debounce_samples: int = 3,
        publisher: Any = None,
    ) -> None:
        self.phone_stand = phone_stand
        self.repo = repo
        self.publisher = publisher
        self.poll_ms = max(20, int(poll_ms))
        self.store = PhoneSessionStore(
            repo,
            debounce_samples=debounce_samples,
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> "PhoneHealth":
        if self.phone_stand is None:
            return PhoneHealth(
                "disabled",
                "no phone stand sensor; manual mode available",
            )
        status = self.phone_stand.probe()
        if not status.available:
            return PhoneHealth(
                "disabled",
                f"phone stand unavailable: {status.detail}",
            )
        self.store.seed(
            _snapshot(self.phone_stand.state())
        )
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll,
            name="flow-phone-sessions",
            daemon=True,
        )
        self._thread.start()
        return PhoneHealth("ok", "phone sessions listening")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def manual(
        self,
        present: bool,
        charging: bool = False,
        *,
        current_ma: int = 0,
    ) -> dict[str, object] | None:
        transition = self.store.manual(
            present,
            charging,
            current_ma=current_ma,
            at=_utc_now(),
        )
        if transition is not None:
            self._publish_phone(transition.snapshot)
        return (
            {
                "kind": transition.kind,
                "session_id": transition.session_id,
                "snapshot": transition.snapshot.__dict__,
            }
            if transition is not None
            else None
        )

    def health(self) -> "PhoneHealth":
        if not self.running:
            if self.phone_stand is None:
                return PhoneHealth(
                    "disabled",
                    "no phone stand sensor; manual mode available",
                )
            return PhoneHealth(
                "error",
                self._last_error or "phone session poll is not running",
            )
        return PhoneHealth("ok", "phone sessions listening")

    def snapshot(self) -> dict[str, object]:
        return {
            "enabled": self.phone_stand is not None,
            "running": self.running,
            "poll_ms": self.poll_ms,
            **self.store.snapshot(),
        }

    def switch_repo(self, repo: PhoneSessionRepository) -> None:
        self.repo = repo
        self.store.repo = repo
        open_session = repo.open_session()
        self.store._session_id = (
            str(open_session["id"]) if open_session is not None else None
        )

    def phone_state(self) -> dict[str, object]:
        state = self.store.stable
        return {
            "present": state.present,
            "charging": state.charging,
            "current_ma": state.current_ma,
            "at": state.at,
        }

    def _poll(self) -> None:
        while not self._stop.wait(self.poll_ms / 1000.0):
            try:
                state = self.phone_stand.state() if self.phone_stand else None
                if state is None:
                    continue
                transition = self.store.observe(
                    state.present,
                    state.charging,
                    current_ma=state.current_ma,
                    at=_utc_now(),
                )
                if transition is not None:
                    logger.info(
                        "phone.transition",
                        extra={
                            "event": "phone.transition",
                            "message_type": transition.kind,
                        },
                    )
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("phone session poll failed")

    def _publish_phone(self, snapshot: PhoneSnapshot) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(
                topics.PHONE_CHANGED,
                {
                    "present": snapshot.present,
                    "charging": snapshot.charging,
                    "current_ma": snapshot.current_ma,
                    "at": snapshot.at or _utc_now(),
                },
            )
        except Exception:  # pragma: no cover - bus boundary
            logger.exception("phone manual event failed")


class PhoneHealth:
    def __init__(self, state: str, detail: str = "") -> None:
        self.state = state
        self.detail = detail

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _snapshot(state: PhoneState) -> PhoneSnapshot:
    return PhoneSnapshot(
        present=state.present,
        charging=state.charging,
        current_ma=state.current_ma,
        at=_utc_now(),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


__all__ = ["PhoneHealth", "PhoneSessionService"]
