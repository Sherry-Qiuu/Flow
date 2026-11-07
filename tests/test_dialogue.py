"""T08 dialogue policy tests."""

from __future__ import annotations

from datetime import datetime

from dialogue.actions import DialogueDispatcher
from dialogue.policy import Dialogue
from dialogue.tools import TOOL_NAMES
from planner.timeutil import tz_for

TZ = tz_for("Asia/Shanghai")


def test_nine_tools_are_fixed():
    assert len(TOOL_NAMES) == 9
    assert set(TOOL_NAMES) == {
        "open_tool",
        "create_task",
        "update_task",
        "delete_task",
        "build_plan",
        "modify_plan",
        "confirm",
        "cancel",
        "query",
    }


def test_two_intents_in_one_sentence():
    dialogue = Dialogue(
        now_fn=lambda: datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    )
    actions = dialogue.turn("打开计时器然后提醒我喝水")
    kinds = [action.kind for action in actions]
    assert "enter_channel" in kinds
    assert "create_task" in kinds


def test_missing_slot_asks_one_question_then_updates():
    dialogue = Dialogue(
        now_fn=lambda: datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    )
    first = dialogue.turn("写物理实验报告")
    assert len(first) == 1
    assert first[0].kind == "ask"
    second = dialogue.turn("后天")
    assert second[0].kind == "update_task"
    assert "2026-11-09" in second[0].payload["value"]


def test_destructive_action_needs_confirmation():
    dialogue = Dialogue()
    ask = dialogue.turn("删掉第二个任务")
    assert ask[0].kind == "ask"
    confirmed = dialogue.turn("确认")
    assert confirmed[0].kind == "delete_task"
    assert confirmed[0].payload["index"] == 2


def test_cancel_and_timeout():
    dialogue = Dialogue()
    ask = dialogue.turn("清空所有任务")
    assert ask[0].kind == "ask"
    cancelled = dialogue.turn("取消")
    assert cancelled[0].kind == "cancel"
    assert dialogue.context.pending is None
    dialogue.context.last_active -= 31
    assert dialogue.context.expire_if_needed()


def test_dispatcher_runs_callbacks():
    calls = []
    dialogue = Dialogue()
    dispatcher = DialogueDispatcher(
        on_channel=lambda payload: calls.append(
            ("channel", payload.get("tool"))
        ),
    )
    actions = dialogue.turn("打开任务清单")
    results = dispatcher.dispatch(actions)
    assert results[0]["ok"] is True
    assert calls == [("channel", "tasks")]
