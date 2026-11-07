"""T13 plan negotiation and T14 focus tests."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from focus.service import FocusService
from planner.models import PlanDraft, PlanItem, SubTask, Task
from planner.timeutil import tz_for
from plan.service import PlanService, conflicts
from scheduler.model import TZ


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"plan-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def make_draft(plan_id: str = "p_demo") -> PlanDraft:
    return PlanDraft(
        plan_id=plan_id,
        date="2026-11-07",
        items=[
            PlanItem(
                task_id="",
                subtask_id="",
                start="19:00",
                end="19:30",
                title="列论点",
                est_minutes=30,
            ),
            PlanItem(
                task_id="",
                subtask_id="",
                start="19:20",
                end="19:50",
                title="写引言",
                est_minutes=30,
            ),
        ],
    )


def test_plan_revise_undo_confirm(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    service = PlanService(repos)
    draft = make_draft()
    repos.plans.save(draft)
    service._versions.setdefault(draft.plan_id, []).append(draft)
    assert conflicts(draft)
    revised = service.revise(draft.plan_id, "推迟 10 分钟")
    assert revised["ok"] is False
    assert "conflict" in revised["reason"]
    # A non-conflicting edit.
    revised = service.revise(draft.plan_id, "缩短 10 分钟")
    assert revised["ok"] is True
    assert revised["plan"]["items"][0]["est_minutes"] == 20
    assert service.undo(draft.plan_id) is not None
    assert service.confirm(draft.plan_id) is not None
    assert repos.plans.get(draft.plan_id) is not None
    database.close()


def test_plan_create_from_tasks(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    task = Task(id="t1", title="写论文", est_minutes=45)
    repos.tasks.create(task)
    service = PlanService(repos)
    draft = service.create([task], day=date(2026, 11, 7))
    assert draft.items
    assert service.summary(draft.plan_id)["items"] == len(draft.items)
    database.close()


def test_focus_advances_and_recovers(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    draft = make_draft("p_focus")
    repos.plans.save(draft)
    store_path = workspace_tmp / f"focus-{uuid.uuid4().hex}.json"
    service = FocusService(
        repos,
        store_path=store_path,
        now_fn=lambda: datetime(2026, 11, 7, 19, 0, tzinfo=TZ),
    )
    service.start()
    try:
        result = service.begin("p_focus")
        assert result["ok"]
        assert service.snapshot()["title"] == "列论点"
        assert service.snapshot()["remaining_ms"] == 1800000
        service.control("pause")
        service.control("resume")
        advanced = service.control("finish")
        assert advanced["ok"]
        assert service.snapshot()["title"] == "写引言"
        service.control("stuck")
        service.control("stuck")
        assert service.snapshot()["total_ms"] <= 300000
        service.control("skip")
        assert service.snapshot()["status"] == "done"
        saved = json.loads(store_path.read_text("utf-8"))
        assert saved["plan_id"] == "p_focus"
    finally:
        service.stop()
        database.close()


def test_focus_recovers_saved_state(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    repos.plans.save(make_draft("p_recover"))
    store_path = workspace_tmp / f"focus-recover-{uuid.uuid4().hex}.json"
    now = datetime(2026, 11, 7, 19, 0, tzinfo=TZ)
    first = FocusService(
        repos,
        store_path=store_path,
        now_fn=lambda: now,
    )
    first.start()
    first.begin("p_recover")
    first.control("pause")
    first.stop()
    second = FocusService(
        repos,
        store_path=store_path,
        now_fn=lambda: now,
    )
    second.start()
    try:
        assert second.snapshot()["title"] == "列论点"
        assert second.snapshot()["status"] == "paused"
    finally:
        second.stop()
        database.close()
