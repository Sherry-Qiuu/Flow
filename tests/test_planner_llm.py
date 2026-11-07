"""T12 LLM main path: reply parsing, degradation and caching."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from planner.engine import RuleEngine
from planner.llm import (
    DecomposeCache,
    LlmEngine,
    LlmError,
    LlmSettings,
    default_engine,
    settings_from_env,
)
from planner.models import Prefs, Task
from planner.validator import is_verb_first

DAY = date(2026, 11, 8)


class FakeClient:
    """Scripted provider: returns a canned reply or raises."""

    def __init__(self, reply=None, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    def complete(self, messages, *, timeout_s=None):  # noqa: ANN001
        self.calls += 1
        self.messages.append(list(messages))
        if self.error is not None:
            raise self.error
        if isinstance(self.reply, str):
            return self.reply
        return json.dumps(self.reply, ensure_ascii=False)


def _steps(*rows: tuple[str, int]) -> list[dict[str, object]]:
    return [
        {
            "title": title,
            "est_minutes": minutes,
            "completion_criteria": f"完成：{title}",
            "difficulty": 2,
        }
        for title, minutes in rows
    ]


ESSAY_STEPS = _steps(
    ("打开文档，列出 3 个核心论点", 20),
    ("整理每个论点的 1 个例子", 30),
    ("写出开头段", 25),
    ("写出三个正文段", 40),
    ("检查引用格式", 20),
)


def _engine(
    reply=None,
    *,
    error: Exception | None = None,
    cache_path: Path | None = None,
    ttl_s: int = 86_400,
    clock=None,
    prefs: Prefs | None = None,
) -> tuple[LlmEngine, FakeClient]:
    client = FakeClient(reply, error)
    engine = LlmEngine(
        prefs or Prefs(),
        settings=LlmSettings(api_key="test-key", cache_ttl_s=ttl_s),
        client=client,
        cache_path=cache_path,
        **({"clock": clock} if clock is not None else {}),
    )
    return engine, client


# -- happy path -------------------------------------------------------
def test_valid_reply_becomes_llm_subtasks():
    engine, client = _engine({"tasks": [{"task_id": "t1", "steps": ESSAY_STEPS}]})
    task = Task(id="t1", title="写 3000 字论文")

    steps = engine.decompose(task)

    assert client.calls == 1
    assert len(steps) == 5
    assert [step.id for step in steps] == [f"t1_s{i}" for i in range(1, 6)]
    assert all(step.source == "llm" for step in steps)
    assert all(is_verb_first(step.title) for step in steps)
    assert all(step.completion_criteria for step in steps)
    assert [step.order for step in steps] == [1, 2, 3, 4, 5]


def test_single_task_reply_without_batch_wrapper_is_accepted():
    engine, _ = _engine({"steps": ESSAY_STEPS})
    steps = engine.decompose(Task(id="t9", title="复习高数"))
    assert len(steps) == 5
    assert all(step.task_id == "t9" for step in steps)


def test_prompt_carries_the_step_rules():
    engine, client = _engine({"tasks": [{"task_id": "t1", "steps": ESSAY_STEPS}]})
    engine.decompose(Task(id="t1", title="写 3000 字论文"))

    prompt = client.messages[0][-1]["content"]
    assert "3-7 步" in prompt
    assert "15-45 分钟" in prompt
    assert "不超过 20 分钟" in prompt
    assert "task_id=t1" in prompt


# -- the caps are enforced on the reply -------------------------------
def test_oversized_steps_are_clamped_to_the_caps():
    reply = {
        "tasks": [
            {
                "task_id": "t1",
                "steps": _steps(
                    ("打开文档，列出 3 个核心论点", 90),
                    ("整理资料", 5),
                    ("写出开头段", 60),
                ),
            }
        ]
    }
    engine, _ = _engine(reply)
    steps = engine.decompose(Task(id="t1", title="写论文"))

    assert steps[0].est_minutes == 20  # first step cap
    assert steps[1].est_minutes == 15  # floor
    assert steps[2].est_minutes == 45  # per-step cap


def test_more_than_seven_steps_are_merged():
    rows = [(f"整理第 {index} 部分", 15) for index in range(1, 11)]
    engine, _ = _engine({"tasks": [{"task_id": "t1", "steps": _steps(*rows)}]})

    steps = engine.decompose(Task(id="t1", title="整理课程笔记"))

    assert len(steps) == 7
    assert steps[-1].est_minutes == 45  # three merged 15-minute steps, capped


def test_too_few_steps_falls_back_to_rules():
    reply = {"tasks": [{"task_id": "t1", "steps": _steps(("打开文档", 20))}]}
    engine, _ = _engine(reply)

    steps = engine.decompose(Task(id="t1", title="写 3000 字论文"))

    assert len(steps) >= 3
    assert all(step.source == "rule" for step in steps)
    assert engine.last_error


def test_non_verb_first_step_falls_back_to_rules():
    reply = {
        "tasks": [
            {
                "task_id": "t1",
                "steps": _steps(
                    ("打开文档", 20),
                    ("论文整体结构", 30),
                    ("写出开头段", 25),
                ),
            }
        ]
    }
    engine, _ = _engine(reply)
    steps = engine.decompose(Task(id="t1", title="写论文"))

    assert all(step.source == "rule" for step in steps)


# -- degradation ------------------------------------------------------
def test_broken_json_falls_back_within_the_rule_engine():
    engine, client = _engine("这不是 JSON")

    steps = engine.decompose(Task(id="t1", title="写 3000 字论文"))

    assert client.calls == 1
    assert all(step.source == "rule" for step in steps)
    assert 3 <= len(steps) <= 7
    assert "JSON" in engine.last_error


def test_provider_failure_falls_back_to_rules():
    engine, _ = _engine(error=LlmError("timeout"))

    steps = engine.decompose(Task(id="t1", title="写 3000 字论文"))

    assert all(step.source == "rule" for step in steps)
    assert "timeout" in engine.last_error


def test_missing_key_never_calls_the_provider():
    engine = LlmEngine(settings=LlmSettings(api_key=""))

    assert engine.usable is False
    steps = engine.decompose(Task(id="t1", title="写 3000 字论文"))
    assert all(step.source == "rule" for step in steps)


def test_default_engine_picks_the_offline_path_without_a_key():
    assert isinstance(default_engine(env={}), RuleEngine)
    llm_engine = default_engine(env={"DEEPSEEK_API_KEY": "k"})
    assert isinstance(llm_engine, LlmEngine)
    assert llm_engine.usable is True


# -- cache ------------------------------------------------------------
def test_reply_is_cached_for_the_next_call(workspace_tmp: Path):
    cache_path = workspace_tmp / "llm_cache_unit.json"
    cache_path.unlink(missing_ok=True)
    engine, client = _engine(
        {"tasks": [{"task_id": "t1", "steps": ESSAY_STEPS}]},
        cache_path=cache_path,
    )
    task = Task(id="t1", title="写 3000 字论文")

    first = engine.decompose(task)
    second = engine.decompose(task)

    assert client.calls == 1
    assert [step.title for step in first] == [step.title for step in second]
    assert cache_path.exists()


def test_cache_entry_expires_after_the_ttl(workspace_tmp: Path):
    cache_path = workspace_tmp / "llm_cache_ttl.json"
    cache_path.unlink(missing_ok=True)
    now = [1_000_000.0]
    engine, client = _engine(
        {"tasks": [{"task_id": "t1", "steps": ESSAY_STEPS}]},
        cache_path=cache_path,
        ttl_s=3600,
        clock=lambda: now[0],
    )
    task = Task(id="t1", title="写 3000 字论文")

    engine.decompose(task)
    now[0] += 3601
    engine.decompose(task)

    assert client.calls == 2


def test_cache_ignores_corrupt_files(workspace_tmp: Path):
    cache_path = workspace_tmp / "llm_cache_corrupt.json"
    cache_path.write_text("{not json", encoding="utf-8")
    cache = DecomposeCache(cache_path, 3600)

    assert cache.get("missing") is None
    cache.put("k", [{"title": "打开文档", "est_minutes": 15}])
    assert cache.get("k") is not None


# -- plan() -----------------------------------------------------------
def test_plan_uses_one_batch_call_and_marks_the_draft():
    reply = {
        "tasks": [
            {"task_id": "t1", "steps": ESSAY_STEPS},
            {
                "task_id": "t2",
                "steps": _steps(
                    ("打开课本翻到第 3 章", 15),
                    ("做课后 5 道习题", 30),
                    ("检查错题并订正", 20),
                ),
            },
        ]
    }
    engine, client = _engine(reply)
    tasks = [
        Task(id="t1", title="写 3000 字论文"),
        Task(id="t2", title="复习高数第 3 章"),
    ]

    draft = engine.plan(DAY, tasks)

    assert client.calls == 1
    assert draft.mode == "llm"
    assert engine.last_mode == "llm"
    assert draft.items
    assert engine.last_validation is not None
    assert engine.last_validation.ok
    assert not any("AI 拆解暂时不可用" in warning for warning in draft.warnings)


def test_plan_falls_back_to_rules_when_the_provider_fails():
    engine, _ = _engine(error=LlmError("network down"))
    tasks = [Task(id="t1", title="写 3000 字论文")]

    draft = engine.plan(DAY, tasks)

    assert draft.mode == "rule"
    assert draft.items
    assert any("AI 拆解暂时不可用" in warning for warning in draft.warnings)
    assert engine.last_validation is not None
    assert engine.last_validation.ok


def test_plan_keeps_existing_subtasks_untouched():
    task = Task(id="t1", title="写 3000 字论文")
    task.subtasks = RuleEngine().decompose(task)
    engine, client = _engine({"tasks": []})

    draft = engine.plan(DAY, [task])

    assert client.calls == 0
    assert draft.mode == "rule"
    assert draft.items


# -- settings ---------------------------------------------------------
def test_settings_read_the_deepseek_key_and_ignore_blank_overrides():
    settings = settings_from_env(
        {"DEEPSEEK_API_KEY": "  sk-test  ", "FLOW_LLM_BASE_URL": ""}
    )

    assert settings.api_key == "sk-test"
    assert settings.available is True
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-chat"


def test_settings_can_be_disabled_by_env():
    settings = settings_from_env(
        {"DEEPSEEK_API_KEY": "sk-test", "FLOW_LLM_ENABLED": "false"}
    )

    assert settings.enabled is False
    assert settings.available is False


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_key_keeps_the_offline_path(value: str):
    settings = settings_from_env({"DEEPSEEK_API_KEY": value})
    assert settings.available is False
