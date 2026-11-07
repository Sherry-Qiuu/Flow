"""Remaining T18/T19/T22/T24/T25/T26/T27/T28/T29/T30 tests."""

from __future__ import annotations

import uuid
from pathlib import Path

from analytics.collector import AnalyticsService
from analytics.distraction import DistractionService, check_tone
from analytics.load import LoadService
from analytics.weekly import WeeklyReportService
from data.database import FlowDatabase, ensure_user
from data.repositories import repositories
from degrade import DegradeMatrix, user_message
from demo.service import DemoService
from hal.factory import create_hal
from phone.inbox import FileInbox
from phone.usage import UsageService
from setup.wizard import first_run_needed, write_first_run_config
from users.service import UserError, UserService


def open_db(root: Path) -> FlowDatabase:
    database = FlowDatabase(root / f"remaining-{uuid.uuid4().hex}.db")
    assert database.start().ok
    ensure_user(database.connection, "u_a", "A")
    return database


def test_analytics_metrics_and_weekly(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    analytics = AnalyticsService(repos)
    analytics.record("step.completed", {"actual_min": 30})
    analytics.record("step.skipped", {})
    analytics.record("rest.offered", {})
    analytics.record("rest.accepted", {})
    metrics = analytics.metrics(7)
    assert metrics["completion_rate"] == 0.5
    assert metrics["rest_accept_rate"] == 1.0
    distraction = DistractionService(repos)
    distraction.log(minutes=10, purpose="leisure", context="卡住了")
    insights = distraction.insights(7)
    assert insights["count"] == 1
    assert insights["total_minutes"] == 10
    assert check_tone("这周你完成了一些小步")
    weekly = WeeklyReportService(
        repos,
        analytics,
        distractions=distraction,
        export_dir=workspace_tmp / f"weekly-{uuid.uuid4().hex}",
    )
    report = weekly.generate(7)
    assert len(report["cards"]) == 3
    assert Path(report["export"]).is_file()
    database.close()


def test_load_and_rest(workspace_tmp):
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    load = LoadService(repos, distractions=DistractionService(repos))
    assert load.snapshot()["level"] == 0
    load.acknowledge(2)
    assert load.snapshot()["suppressed"] is True
    assert user_message("asr")
    database.close()


def test_inbox_and_usage_privacy(workspace_tmp):
    inbox = FileInbox(workspace_tmp / f"inbox-{uuid.uuid4().hex}")
    saved = inbox.save("作业.pdf", b"%PDF-1.4 test")
    assert saved["ok"] is True
    assert inbox.list()[0]["status"] == "pending"
    try:
        inbox.save("x.exe", b"nope")
        raise AssertionError("exe should be rejected")
    except ValueError:
        pass
    usage = UsageService(workspace_tmp / "usage.json", enabled=False)
    assert usage.ingest({"com.x": 10})["accepted"] is False
    usage.set_enabled(True)
    assert usage.ingest({"com.x": 10})["accepted"] is True
    assert usage.top(5)[0]["package"] == "com.x"
    assert "iOS" in usage.status()["ios"]


def test_users_export_delete_and_isolation(workspace_tmp):
    database = open_db(workspace_tmp)
    users = UserService(database.connection)
    created = users.create("小 B", nickname="B")
    users.switch(created["id"])
    repos = users.repos(created["id"])
    from planner.models import Task

    repos.tasks.create(Task(id="t_b", title="B 的任务"))
    assert repos.tasks.get("t_b") is not None
    assert users.repos("u_a").tasks.get("t_b") is None
    exported = users.export(created["id"])
    assert exported["user"]["name"] == "小 B"
    assert exported["tasks"][0]["title"] == "B 的任务"
    try:
        users.delete(created["id"])
        raise AssertionError("delete needs confirm")
    except UserError:
        pass
    assert users.delete(created["id"], confirm=True) is True
    database.close()


def test_first_run_demo_and_degrade(workspace_tmp):
    config = workspace_tmp / f"config-{uuid.uuid4().hex}.yaml"
    write_first_run_config(
        config,
        name="小 A",
        nickname="A",
        voice="zh",
        chronotype="morning",
    )
    assert first_run_needed(config) is False
    database = open_db(workspace_tmp)
    repos = repositories(database.connection, "u_a")
    demo = DemoService(
        repos,
        connection=database.connection,
        marker=workspace_tmp / "demo.json",
    )
    result = demo.reset()
    assert result["ok"] and len(result["tasks"]) == 3
    assert repos.tasks.list()
    matrix = DegradeMatrix(create_hal("mock"))
    assert "items" in matrix.snapshot()
    database.close()
