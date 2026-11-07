"""Rule decomposition tests."""

from __future__ import annotations

import pytest

from planner import (
    Category,
    Prefs,
    SubTask,
    Task,
    decompose,
    estimate_minutes,
    infer_category,
    is_verb_first,
)
from planner.templates import TEMPLATES


class FakeHistory:
    def __init__(self, minutes: int) -> None:
        self.minutes = minutes

    def median_minutes(self, category, title):
        return self.minutes


def test_essay_decomposition_meets_contract():
    task = Task(id="t1", title="写 3000 字论文")
    subtasks = decompose(task)
    assert 3 <= len(subtasks) <= 7
    assert sum(item.est_minutes for item in subtasks) == 180
    assert subtasks[0].title == "打开文档，列出 3 个核心论点"
    assert subtasks[0].est_minutes <= 20
    assert all(15 <= item.est_minutes <= 45 for item in subtasks)
    assert all(is_verb_first(item.title) for item in subtasks)
    assert all(item.completion_criteria for item in subtasks)


@pytest.mark.parametrize("category", list(Category))
def test_every_category_produces_valid_steps(category):
    task = Task(
        id=f"t_{category.value}",
        title=f"完成 {category.value} 任务",
        category=category,
        est_minutes=120,
    )
    subtasks = decompose(task)
    assert 3 <= len(subtasks) <= 7
    assert sum(item.est_minutes for item in subtasks) == 120
    assert subtasks[0].est_minutes <= 20
    assert all(15 <= item.est_minutes <= 45 for item in subtasks)
    assert all(is_verb_first(item.title) for item in subtasks)


def test_long_task_is_capped_at_seven_steps():
    task = Task(id="big", title="完成一个很大的项目", est_minutes=600)
    subtasks = decompose(task)
    assert len(subtasks) == 7
    assert sum(item.est_minutes for item in subtasks) == 290
    assert subtasks[0].est_minutes <= 20
    assert all(item.est_minutes <= 45 for item in subtasks)


def test_tiny_task_gets_minimum_three_steps():
    task = Task(id="tiny", title="回复一封邮件", est_minutes=10)
    subtasks = decompose(task)
    assert len(subtasks) == 3
    assert sum(item.est_minutes for item in subtasks) == 45
    assert all(item.est_minutes == 15 for item in subtasks)


def test_history_median_overrides_rule_table():
    task = Task(id="hist", title="写课程论文提纲")
    subtasks = decompose(task, history=FakeHistory(100))
    assert sum(item.est_minutes for item in subtasks) == 100
    assert len(subtasks) == 4


def test_existing_subtasks_are_not_rewritten():
    existing = [
        SubTask(
            id="x_s1",
            task_id="x",
            title="打开文档写提纲",
            est_minutes=20,
            order=1,
        )
    ]
    task = Task(id="x", title="写提纲", subtasks=existing)
    assert decompose(task) == existing


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("写 3000 字论文", Category.WRITING),
        ("读完第 3 章教材", Category.READING),
        ("背 50 个单词", Category.MEMORIZATION),
        ("完成物理实验数据采集", Category.EXPERIMENT),
        ("准备小组讨论", Category.DISCUSSION),
        ("实现登录接口并写测试", Category.CODING),
        ("购买生活用品", Category.GENERAL),
    ],
)
def test_category_inference(title, expected):
    assert infer_category(Task(id="t", title=title)) is expected


def test_explicit_category_wins():
    task = Task(id="t", title="写 3000 字论文", category=Category.READING)
    assert infer_category(task) is Category.READING


def test_estimate_parses_chinese_character_count():
    task = Task(id="t", title="写 3000 字论文")
    assert estimate_minutes(task) == 180


def test_estimate_parses_page_count():
    task = Task(id="t", title="阅读 50 页教材")
    assert estimate_minutes(task) >= 75


def test_all_template_titles_start_with_verbs():
    for category, templates in TEMPLATES.items():
        for template in templates:
            title = template.title.format(task="示例任务")
            assert is_verb_first(title), (category, title)
