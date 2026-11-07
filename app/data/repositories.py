"""T10 repositories: every business query is scoped to one user_id."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from typing import Any

from data.mapping import (
    plan_from_rows,
    plan_item_to_row,
    plan_to_row,
    subtask_from_row,
    subtask_to_row,
    task_from_row,
    task_to_row,
)
from planner.models import PlanDraft, SubTask, Task


class RepositoryError(RuntimeError):
    pass


class BaseRepository:
    def __init__(self, connection: sqlite3.Connection, user_id: str) -> None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required for every repository")
        self.connection = connection
        self.user_id = user_id

    def _execute(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def _one(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> sqlite3.Row | None:
        return self._execute(sql, params).fetchone()

    def _all(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[sqlite3.Row]:
        return list(self._execute(sql, params).fetchall())

    def _insert(self, table: str, data: dict[str, Any]) -> None:
        columns = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        self.connection.commit()


class UserRepository(BaseRepository):
    def get(self) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM users WHERE id = ?", (self.user_id,))
        return dict(row) if row else None

    def ensure(self, name: str, nickname: str = "") -> None:
        self._execute(
            "INSERT OR IGNORE INTO users "
            "(id, name, nickname, created_at, settings_json) "
            "VALUES (?, ?, ?, ?, '{}')",
            (self.user_id, name, nickname, utc_now()),
        )
        self.connection.commit()


class TaskRepository(BaseRepository):
    def create(self, task: Task) -> Task:
        self._insert("tasks", task_to_row(task, self.user_id))
        return task

    def upsert(self, task: Task) -> Task:
        existing = self._one(
            "SELECT user_id FROM tasks WHERE id = ?",
            (task.id,),
        )
        if existing is not None and existing["user_id"] != self.user_id:
            raise RepositoryError("task id belongs to another user")
        row = task_to_row(task, self.user_id)
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        updates = ", ".join(
            f"{column}=excluded.{column}"
            for column in row
            if column not in {"id", "user_id"}
        )
        self._execute(
            f"INSERT INTO tasks ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            tuple(row.values()),
        )
        self.connection.commit()
        return task

    def get(
        self,
        task_id: str,
        *,
        include_deleted: bool = False,
    ) -> Task | None:
        deleted = "" if include_deleted else " AND deleted_at IS NULL"
        row = self._one(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?" + deleted,
            (task_id, self.user_id),
        )
        return task_from_row(row) if row else None

    def list(
        self,
        *,
        status: str | None = None,
        include_deleted: bool = False,
    ) -> list[Task]:
        clauses = ["user_id = ?"]
        params: list[Any] = [self.user_id]
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        rows = self._all(
            "SELECT * FROM tasks WHERE "
            + " AND ".join(clauses)
            + " ORDER BY priority ASC, due_at ASC, created_at ASC",
            tuple(params),
        )
        return [task_from_row(row) for row in rows]

    def update_status(self, task_id: str, status: str) -> bool:
        cursor = self._execute(
            "UPDATE tasks SET status = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (status, utc_now(), task_id, self.user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def soft_delete(self, task_id: str) -> bool:
        cursor = self._execute(
            "UPDATE tasks SET deleted_at = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (utc_now(), utc_now(), task_id, self.user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def subtasks(self, task_id: str) -> list[SubTask]:
        rows = self._all(
            "SELECT s.* FROM subtasks s JOIN tasks t ON t.id = s.task_id "
            "WHERE s.task_id = ? AND t.user_id = ? "
            "ORDER BY s.order_index ASC",
            (task_id, self.user_id),
        )
        return [subtask_from_row(row) for row in rows]


class SubTaskRepository(BaseRepository):
    def create(self, subtask: SubTask) -> SubTask:
        self._require_task(subtask.task_id)
        self._insert("subtasks", subtask_to_row(subtask))
        return subtask

    def list(self, task_id: str) -> list[SubTask]:
        self._require_task(task_id)
        rows = self._all(
            "SELECT * FROM subtasks WHERE task_id = ? "
            "ORDER BY order_index ASC",
            (task_id,),
        )
        return [subtask_from_row(row) for row in rows]

    def mark_done(self, subtask_id: str, done: bool = True) -> bool:
        cursor = self._execute(
            "UPDATE subtasks SET done_at = ? WHERE id = ? AND task_id IN "
            "(SELECT id FROM tasks WHERE user_id = ?)",
            (utc_now() if done else None, subtask_id, self.user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def _require_task(self, task_id: str) -> None:
        row = self._one(
            "SELECT 1 FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, self.user_id),
        )
        if row is None:
            raise RepositoryError("task does not belong to this user")


class PlanRepository(BaseRepository):
    def save(self, draft: PlanDraft) -> PlanDraft:
        existing = self._one(
            "SELECT user_id FROM plans WHERE id = ?",
            (draft.plan_id,),
        )
        if existing is not None and existing["user_id"] != self.user_id:
            raise RepositoryError("plan id belongs to another user")
        plan_row = plan_to_row(draft, self.user_id)
        columns = ", ".join(plan_row)
        placeholders = ", ".join("?" for _ in plan_row)
        self._execute(
            f"INSERT INTO plans ({columns}) VALUES ({placeholders}) "
            "ON CONFLICT(id) DO UPDATE SET "
            "status=excluded.status, version=plans.version + 1, "
            "breaks_json=excluded.breaks_json, "
            "notes_json=excluded.notes_json, "
            "warnings_json=excluded.warnings_json, "
            "mode=excluded.mode, updated_at=excluded.updated_at",
            tuple(plan_row.values()),
        )
        self._execute("DELETE FROM plan_items WHERE plan_id = ?",
                      (draft.plan_id,))
        for index, item in enumerate(draft.items):
            self._insert_plan_item(
                plan_item_to_row(
                    item,
                    draft.plan_id,
                    plan_date=draft.date,
                    order_index=index,
                )
            )
        self.connection.commit()
        return draft

    def get(self, plan_id: str) -> PlanDraft | None:
        row = self._one(
            "SELECT * FROM plans WHERE id = ? AND user_id = ?",
            (plan_id, self.user_id),
        )
        if row is None:
            return None
        items = self._all(
            "SELECT i.* FROM plan_items i JOIN plans p ON p.id = i.plan_id "
            "WHERE i.plan_id = ? AND p.user_id = ? "
            "ORDER BY i.order_index ASC",
            (plan_id, self.user_id),
        )
        return plan_from_rows(row, items)

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM plans WHERE user_id = ? "
            "ORDER BY plan_date DESC LIMIT ?",
            (self.user_id, max(1, int(limit))),
        )
        return [dict(row) for row in rows]

    def _insert_plan_item(self, data: dict[str, Any]) -> None:
        columns = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO plan_items ({columns}) VALUES ({placeholders})",
            tuple(data.values()),
        )


class PlanItemRepository(BaseRepository):
    def list(self, plan_id: str) -> list[dict[str, Any]]:
        self._require_plan(plan_id)
        rows = self._all(
            "SELECT * FROM plan_items WHERE plan_id = ? "
            "ORDER BY order_index ASC",
            (plan_id,),
        )
        return [dict(row) for row in rows]

    def update_status(self, item_id: str, status: str) -> bool:
        cursor = self._execute(
            "UPDATE plan_items SET status = ? WHERE id = ? AND plan_id IN "
            "(SELECT id FROM plans WHERE user_id = ?)",
            (status, item_id, self.user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def _require_plan(self, plan_id: str) -> None:
        row = self._one(
            "SELECT 1 FROM plans WHERE id = ? AND user_id = ?",
            (plan_id, self.user_id),
        )
        if row is None:
            raise RepositoryError("plan does not belong to this user")


class FocusSessionRepository(BaseRepository):
    def start(
        self,
        *,
        plan_item_id: str | None = None,
        started_at: str | None = None,
    ) -> str:
        session_id = new_id("focus")
        self._insert(
            "focus_sessions",
            {
                "id": session_id,
                "user_id": self.user_id,
                "plan_item_id": plan_item_id,
                "started_at": started_at or utc_now(),
                "ended_at": None,
                "interruptions_json": "[]",
            },
        )
        return session_id

    def finish(
        self,
        session_id: str,
        *,
        ended_at: str | None = None,
        interruptions: list[dict[str, Any]] | None = None,
    ) -> bool:
        cursor = self._execute(
            "UPDATE focus_sessions SET ended_at = ?, interruptions_json = ? "
            "WHERE id = ? AND user_id = ?",
            (
                ended_at or utc_now(),
                json.dumps(interruptions or [], ensure_ascii=False),
                session_id,
                self.user_id,
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM focus_sessions WHERE user_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (self.user_id, max(1, int(limit))),
        )
        return [dict(row) for row in rows]


class ReminderRepository(BaseRepository):
    def create(
        self,
        *,
        kind: str,
        spec: dict[str, Any],
        next_fire_at: str | None,
    ) -> str:
        reminder_id = new_id("rem")
        self._insert(
            "reminders",
            {
                "id": reminder_id,
                "user_id": self.user_id,
                "kind": kind,
                "spec_json": json.dumps(spec, ensure_ascii=False),
                "next_fire_at": next_fire_at,
                "enabled": 1,
                "last_fired_at": None,
                "created_at": utc_now(),
            },
        )
        return reminder_id

    def due(self, now: str | None = None) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM reminders WHERE user_id = ? AND enabled = 1 "
            "AND next_fire_at IS NOT NULL AND next_fire_at <= ? "
            "ORDER BY next_fire_at ASC",
            (self.user_id, now or utc_now()),
        )
        return [dict(row) for row in rows]

    def get(self, reminder_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, self.user_id),
        )
        return dict(row) if row else None

    def list_all(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        clause = " AND enabled = 1" if enabled_only else ""
        rows = self._all(
            "SELECT * FROM reminders WHERE user_id = ?"
            + clause
            + " ORDER BY next_fire_at ASC",
            (self.user_id,),
        )
        return [dict(row) for row in rows]

    def upcoming(
        self,
        now: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        until = (
            datetime.fromisoformat(now.replace("Z", "+00:00"))
            + timedelta(hours=max(1, hours))
        ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        rows = self._all(
            "SELECT * FROM reminders WHERE user_id = ? AND enabled = 1 "
            "AND next_fire_at IS NOT NULL "
            "AND next_fire_at >= ? AND next_fire_at <= ? "
            "ORDER BY next_fire_at ASC",
            (self.user_id, now, until),
        )
        return [dict(row) for row in rows]

    def disable(self, reminder_id: str) -> bool:
        cursor = self._execute(
            "UPDATE reminders SET enabled = 0, next_fire_at = NULL "
            "WHERE id = ? AND user_id = ?",
            (reminder_id, self.user_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0


    def mark_fired(
        self,
        reminder_id: str,
        *,
        next_fire_at: str | None = None,
        fired_at: str | None = None,
    ) -> bool:
        cursor = self._execute(
            "UPDATE reminders SET last_fired_at = ?, next_fire_at = ?, "
            "enabled = CASE WHEN ? IS NULL THEN 0 ELSE enabled END "
            "WHERE id = ? AND user_id = ?",
            (
                fired_at or utc_now(),
                next_fire_at,
                next_fire_at,
                reminder_id,
                self.user_id,
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0


class PhoneSessionRepository(BaseRepository):
    def start(
        self,
        *,
        purpose: str = "phone",
        planned_minutes: int | None = None,
        started_at: str | None = None,
        present_state: str = "placed",
    ) -> str:
        session_id = new_id("phone")
        self._insert(
            "phone_sessions",
            {
                "id": session_id,
                "user_id": self.user_id,
                "purpose": purpose,
                "planned_minutes": planned_minutes,
                "started_at": started_at or utc_now(),
                "ended_at": None,
                "returned_on_time": None,
                "present_state": present_state,
            },
        )
        return session_id

    def finish(
        self,
        session_id: str,
        *,
        ended_at: str | None = None,
        returned_on_time: bool | None = None,
    ) -> bool:
        cursor = self._execute(
            "UPDATE phone_sessions SET ended_at = ?, returned_on_time = ? "
            "WHERE id = ? AND user_id = ? AND ended_at IS NULL",
            (
                ended_at or utc_now(),
                None if returned_on_time is None else int(returned_on_time),
                session_id,
                self.user_id,
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def open_session(self) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM phone_sessions WHERE user_id = ? "
            "AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (self.user_id,),
        )
        return dict(row) if row else None

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM phone_sessions WHERE user_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (self.user_id, max(1, int(limit))),
        )
        return [dict(row) for row in rows]


class DistractionRepository(BaseRepository):
    def add(self, kind: str, note: str = "") -> str:
        event_id = new_id("distraction")
        self._insert(
            "distractions",
            {
                "id": event_id,
                "user_id": self.user_id,
                "kind": kind,
                "note": note,
                "created_at": utc_now(),
            },
        )
        return event_id


class RewardEventRepository(BaseRepository):
    def add(
        self,
        kind: str,
        *,
        points: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_id("reward")
        self._insert(
            "reward_events",
            {
                "id": event_id,
                "user_id": self.user_id,
                "kind": kind,
                "points": int(points),
                "payload_json": json.dumps(payload or {}, ensure_ascii=False),
                "created_at": utc_now(),
            },
        )
        return event_id

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM reward_events WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (self.user_id, max(1, int(limit))),
        )
        return [dict(row) for row in rows]


class CompanionRepository(BaseRepository):
    def get(self) -> dict[str, Any]:
        row = self._one(
            "SELECT * FROM companion_state WHERE user_id = ?",
            (self.user_id,),
        )
        return dict(row) if row else {}

    def set(self, state: dict[str, Any]) -> None:
        self._execute(
            "INSERT INTO companion_state (user_id, state_json, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
            "state_json=excluded.state_json, updated_at=excluded.updated_at",
            (self.user_id, json.dumps(state, ensure_ascii=False), utc_now()),
        )
        self.connection.commit()


class DeviceEventRepository(BaseRepository):
    def add(self, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id("device")
        self._insert(
            "device_events",
            {
                "id": event_id,
                "user_id": self.user_id,
                "type": event_type,
                "payload_json": json.dumps(payload, ensure_ascii=False),
                "ts": utc_now(),
            },
        )
        return event_id


class MetricsRepository(BaseRepository):
    def upsert(
        self,
        day: str | date,
        payload: dict[str, Any],
    ) -> None:
        metric_date = day.isoformat() if isinstance(day, date) else str(day)
        self._execute(
            "INSERT INTO metrics_daily "
            "(id, user_id, metric_date, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, metric_date) DO UPDATE SET "
            "payload_json=excluded.payload_json",
            (
                new_id("metric"),
                self.user_id,
                metric_date,
                json.dumps(payload, ensure_ascii=False),
                utc_now(),
            ),
        )
        self.connection.commit()

    def get(self, day: str | date) -> dict[str, Any] | None:
        metric_date = day.isoformat() if isinstance(day, date) else str(day)
        row = self._one(
            "SELECT * FROM metrics_daily "
            "WHERE user_id = ? AND metric_date = ?",
            (self.user_id, metric_date),
        )
        return dict(row) if row else None


class SettingsRepository(BaseRepository):
    def get(self, scope: str = "default") -> dict[str, Any]:
        row = self._one(
            "SELECT payload_json FROM settings "
            "WHERE user_id = ? AND scope = ?",
            (self.user_id, scope),
        )
        return json.loads(row["payload_json"]) if row else {}

    def set(self, payload: dict[str, Any], scope: str = "default") -> None:
        self._execute(
            "INSERT INTO settings (user_id, scope, payload_json, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, scope) DO UPDATE SET "
            "payload_json=excluded.payload_json, "
            "updated_at=excluded.updated_at",
            (
                self.user_id,
                scope,
                json.dumps(payload, ensure_ascii=False),
                utc_now(),
            ),
        )
        self.connection.commit()


class Repositories:
    """Per-user repository bundle; the only supported entry point for data."""

    def __init__(self, connection: sqlite3.Connection, user_id: str) -> None:
        self.user_id = user_id
        self.users = UserRepository(connection, user_id)
        self.tasks = TaskRepository(connection, user_id)
        self.subtasks = SubTaskRepository(connection, user_id)
        self.plans = PlanRepository(connection, user_id)
        self.plan_items = PlanItemRepository(connection, user_id)
        self.focus_sessions = FocusSessionRepository(connection, user_id)
        self.reminders = ReminderRepository(connection, user_id)
        self.phone_sessions = PhoneSessionRepository(connection, user_id)
        self.distractions = DistractionRepository(connection, user_id)
        self.rewards = RewardEventRepository(connection, user_id)
        self.companion = CompanionRepository(connection, user_id)
        self.device_events = DeviceEventRepository(connection, user_id)
        self.metrics = MetricsRepository(connection, user_id)
        self.settings = SettingsRepository(connection, user_id)


def repositories(
    connection: sqlite3.Connection,
    user_id: str,
) -> Repositories:
    return Repositories(connection, user_id)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
