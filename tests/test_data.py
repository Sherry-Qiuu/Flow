"""T10 schema, repositories, mapping, backup and restore."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from data.backup import backup_database, restore_database
from data.database import FlowDatabase, ensure_user
from data.mapping import (
    plan_from_rows,
    plan_item_to_row,
    plan_to_row,
    task_from_row,
    task_to_row,
)
from data.migrate import CORE_TABLES, current_version, migrate
from data.repositories import RepositoryError, repositories
from planner.models import PlanDraft, PlanItem, SubTask, Task


def db_path(root: Path) -> Path:
    return root / f"flow-{uuid.uuid4().hex}.db"


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(db_path(root))
    health = database.start()
    assert health.ok, health.detail
    ensure_user(database.connection, "u_a", "A")
    ensure_user(database.connection, "u_b", "B")
    return database


def test_schema_and_idempotent_migration(workspace_tmp):
    path = db_path(workspace_tmp)
    with sqlite3.connect(path) as connection:
        first = migrate(connection)
        second = migrate(connection)
        assert first.version == 1
        assert second.version == 1
        assert current_version(connection) == 1
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {row[0] for row in rows}
        assert set(CORE_TABLES) <= names
        assert "schema_version" in names
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()[0] == 1


def test_wal_and_health(workspace_tmp):
    database = open_db(workspace_tmp)
    assert database.health().ok
    mode = database.connection.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0]
    assert mode.lower() == "wal"
    database.close()
    assert not database.health().ok


def test_task_repositories_enforce_user_isolation(workspace_tmp):
    database = open_db(workspace_tmp)
    a = repositories(database.connection, "u_a")
    b = repositories(database.connection, "u_b")
    task = Task(id="t_a", title="A 的任务", est_minutes=30)
    a.tasks.create(task)
    assert a.tasks.get("t_a") is not None
    assert b.tasks.get("t_a") is None
    assert b.tasks.list() == []
    assert b.tasks.update_status("t_a", "done") is False
    assert b.tasks.soft_delete("t_a") is False
    with pytest.raises(RepositoryError):
        b.subtasks.create(
            SubTask(id="s_x", task_id="t_a", title="x", est_minutes=5)
        )
    subtask = SubTask(id="s_a", task_id="t_a", title="列提纲", est_minutes=10)
    a.subtasks.create(subtask)
    assert len(a.subtasks.list("t_a")) == 1
    assert b.subtasks.mark_done("s_a") is False
    database.close()


def test_plan_mapping_roundtrip(workspace_tmp):
    database = open_db(workspace_tmp)
    a = repositories(database.connection, "u_a")
    draft = PlanDraft(
        plan_id="p_20261107",
        date="2026-11-07",
        items=[
            PlanItem(
                task_id="",
                subtask_id="",
                start="19:00",
                end="19:20",
                title="列出论点",
                est_minutes=20,
            )
        ],
    )
    a.plans.save(draft)
    loaded = a.plans.get("p_20261107")
    assert loaded is not None
    assert loaded.items[0].title == "列出论点"
    assert loaded.items[0].start == "19:00"
    assert loaded.items[0].end == "19:20"
    assert a.plan_items.list("p_20261107")[0]["order_index"] == 0
    assert a.plan_items.update_status("p_20261107_i0", "done") is True
    assert repositories(database.connection, "u_b").plans.get(
        "p_20261107"
    ) is None
    database.close()


def test_task_and_plan_mapping_time_is_utc(workspace_tmp):
    task = Task(
        id="t_time",
        title="写论文",
        description="3000 字",
        deadline=datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc),
        est_minutes=45,
    )
    row = task_to_row(task, "u_a")
    assert row["due_at"].endswith("Z")
    loaded = task_from_row(dict(row))
    assert loaded.deadline is not None
    assert loaded.deadline.hour == 20
    assert loaded.id == "t_time"
    assert loaded.description == "3000 字"

    draft = PlanDraft(plan_id="p_time", date="2026-11-07")
    plan_row = plan_to_row(draft, "u_a")
    item_row = plan_item_to_row(
        PlanItem(
            task_id="t_time",
            subtask_id="s_time",
            start="19:00",
            end="20:00",
            title="写",
            est_minutes=60,
        ),
        "p_time",
        plan_date="2026-11-07",
        order_index=0,
    )
    loaded_draft = plan_from_rows(plan_row, [item_row])
    assert loaded_draft.items[0].start == "19:00"
    assert item_row["start_at"].endswith("Z")


def test_phone_sessions_and_other_repositories(workspace_tmp):
    database = open_db(workspace_tmp)
    a = repositories(database.connection, "u_a")
    session_id = a.phone_sessions.start(
        purpose="study",
        planned_minutes=20,
    )
    assert a.phone_sessions.open_session()["id"] == session_id
    assert a.phone_sessions.finish(session_id, returned_on_time=True)
    assert a.phone_sessions.open_session() is None
    assert len(a.phone_sessions.list()) == 1

    reminder = a.reminders.create(
        kind="timer",
        spec={"minutes": 20},
        next_fire_at="2026-11-07T12:00:00Z",
    )
    assert a.reminders.due("2026-11-07T12:01:00Z")[0]["id"] == reminder
    assert a.reminders.mark_fired(reminder) is True

    a.metrics.upsert(date(2026, 11, 7), {"focus_minutes": 40})
    assert a.metrics.get("2026-11-07")["payload_json"]
    a.settings.set({"theme": "warm"})
    assert a.settings.get()["theme"] == "warm"
    a.companion.set({"mood": "happy"})
    assert a.companion.get()["state_json"]
    assert a.device_events.add("boot", {"ok": True})
    assert a.rewards.add("step", points=5)
    assert a.distractions.add("phone")
    database.close()


def test_backup_restore_and_retention(workspace_tmp):
    database = open_db(workspace_tmp)
    a = repositories(database.connection, "u_a")
    a.tasks.create(Task(id="t_before", title="before"))
    backup_path = database.backup_now()
    assert backup_path.is_file()
    a.tasks.create(Task(id="t_after", title="after"))
    assert a.tasks.get("t_after") is not None
    database.close()

    restore_database(backup_path, database.path)
    reopened = FlowDatabase(database.path)
    assert reopened.start().ok
    again = repositories(reopened.connection, "u_a")
    assert again.tasks.get("t_before") is not None
    assert again.tasks.get("t_after") is None
    reopened.close()


def test_restore_rejects_non_sqlite_file(workspace_tmp):
    path = workspace_tmp / f"bad-{uuid.uuid4().hex}.db"
    path.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(RuntimeError):
        restore_database(path, workspace_tmp / "target.db")


def test_backup_retention_keeps_latest(workspace_tmp):
    database = open_db(workspace_tmp)
    for _ in range(4):
        backup_database(
            database.path,
            backup_dir=workspace_tmp / "retention",
            keep=2,
        )
    backups = sorted((workspace_tmp / "retention").glob("flow-*.db"))
    assert len(backups) == 2
    database.close()


def test_corrupt_database_recovers_from_latest_backup(workspace_tmp):
    database = open_db(workspace_tmp)
    repositories(database.connection, "u_a").tasks.create(
        Task(id="t_recover", title="recover")
    )
    backup = database.backup_now()
    assert backup.is_file()
    database.close()
    database.path.write_bytes(b"not sqlite anymore")
    recovered = FlowDatabase(database.path, backup_dir=backup.parent)
    health = recovered.start()
    assert health.ok, health.detail
    assert repositories(recovered.connection, "u_a").tasks.get("t_recover")
    recovered.close()


def test_restore_cli_latest(workspace_tmp):
    from data.restore import main

    database = open_db(workspace_tmp)
    a = repositories(database.connection, "u_a")
    a.tasks.create(Task(id="t_cli", title="cli backup"))
    backup_dir = workspace_tmp / f"cli-backup-{uuid.uuid4().hex}"
    backup_database(
        database.path,
        backup_dir=backup_dir,
        keep=7,
    )
    database.close()
    result = main(
        [
            "--db",
            str(database.path),
            "--backup-dir",
            str(backup_dir),
            "--latest",
        ]
    )
    assert result == 0
    reopened = FlowDatabase(database.path)
    assert reopened.start().ok
    assert repositories(reopened.connection, "u_a").tasks.get("t_cli")
    reopened.close()
