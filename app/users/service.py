"""T24/T25 user accounts, roles, preferences, export and purge."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from data.locking import get_connection_lock
from data.repositories import Repositories, repositories

logger = logging.getLogger(__name__)
DEFAULT_PREFS = {
    "theme": "warm",
    "voice": "zh",
    "quiet_start": 22,
    "quiet_end": 7,
    "tone": "warm",
    "leisure_limit_min": 60,
    "chronotype": "neutral",
}


class UserError(RuntimeError):
    pass


class UserService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        active_user_id: str = "u_default",
    ) -> None:
        self.connection = connection
        self.active_user_id = active_user_id
        self._lock = get_connection_lock(connection)

    def list(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, name, nickname, created_at, settings_json "
            "FROM users ORDER BY created_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, user_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def create(
        self,
        name: str,
        *,
        nickname: str = "",
        role: str = "member",
    ) -> dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise UserError("name is required")
        user_id = f"u_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        settings = json.dumps({"role": role}, ensure_ascii=False)
        with self._lock:
            self.connection.execute(
                "INSERT INTO users "
                "(id, name, nickname, created_at, settings_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, name, nickname, now, settings),
            )
            self.connection.commit()
        repos = repositories(self.connection, user_id)
        repos.settings.set(DEFAULT_PREFS)
        return {
            "id": user_id,
            "name": name,
            "nickname": nickname,
            "role": role,
        }

    def switch(self, user_id: str) -> dict[str, Any]:
        user = self.get(user_id)
        if user is None:
            raise UserError("user not found")
        self.active_user_id = user_id
        return user

    def repos(self, user_id: str | None = None) -> Repositories:
        return repositories(self.connection, user_id or self.active_user_id)

    def prefs(self, user_id: str | None = None) -> dict[str, Any]:
        return {
            **DEFAULT_PREFS,
            **self.repos(user_id).settings.get(),
        }

    def set_prefs(
        self,
        values: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        owned = self.repos(user_id)
        merged = {**DEFAULT_PREFS, **owned.settings.get(), **values}
        owned.settings.set(merged)
        return merged

    def export(self, user_id: str) -> dict[str, Any]:
        repos = self.repos(user_id)
        return {
            "user": self.get(user_id),
            "prefs": self.prefs(user_id),
            "tasks": [task.to_dict() for task in repos.tasks.list()],
            "plans": repos.plans.list(limit=100),
            "reminders": repos.reminders.list_all(),
            "focus_sessions": repos.focus_sessions.list(limit=500),
            "phone_sessions": repos.phone_sessions.list(limit=500),
            "distractions": repos.distractions.list(limit=500),
            "rewards": repos.rewards.list(limit=500),
            "events": repos.device_events.list(limit=1000),
            "metrics": [
                repos.metrics.get(day)
                for day in _recent_days(7)
                if repos.metrics.get(day) is not None
            ],
            "companion": repos.companion.get(),
            "settings": repos.settings.get(),
        }

    def delete(self, user_id: str, *, confirm: bool = False) -> bool:
        if not confirm:
            raise UserError("confirm=true is required")
        if self.get(user_id) is None:
            return False
        tables = (
            "focus_sessions",
            "phone_sessions",
            "reminders",
            "distractions",
            "reward_events",
            "device_events",
            "metrics_daily",
            "settings",
            "companion_state",
            "plans",
            "tasks",
        )
        with self._lock:
            for table in tables:
                self.connection.execute(
                    f"DELETE FROM {table} WHERE user_id = ?",
                    (user_id,),
                )
            self.connection.execute(
                "DELETE FROM subtasks WHERE task_id IN "
                "(SELECT id FROM tasks WHERE user_id = ?)",
                (user_id,),
            )
            self.connection.execute(
                "DELETE FROM plan_items WHERE plan_id IN "
                "(SELECT id FROM plans WHERE user_id = ?)",
                (user_id,),
            )
            self.connection.execute(
                "DELETE FROM users WHERE id = ?",
                (user_id,),
            )
            self.connection.commit()
        return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _recent_days(count: int) -> list[str]:
    from datetime import date, timedelta

    today = date.today()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(count)
    ]
