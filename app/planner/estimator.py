"""Duration estimation and category inference for rule-based planning."""

from __future__ import annotations

import re
from typing import Protocol

from planner.models import Category, Task

_CATEGORY_BASE = {
    Category.READING: 60,
    Category.WRITING: 120,
    Category.MEMORIZATION: 40,
    Category.EXPERIMENT: 120,
    Category.DISCUSSION: 60,
    Category.CODING: 90,
    Category.PRACTICE: 60,
    Category.PRESENTATION: 90,
    Category.GENERAL: 60,
}

_KEYWORDS: tuple[tuple[Category, tuple[str, ...]], ...] = (
    (
        Category.CODING,
        (
            "代码",
            "编程",
            "写代码",
            "调试",
            "开发",
            "接口",
            "实现",
            "测试",
            "coding",
            "code",
            "programming",
            "debug",
            "bug",
        ),
    ),
    (
        Category.EXPERIMENT,
        (
            "实验",
            "试验",
            "lab",
            "experiment",
            "测量",
            "数据采集",
        ),
    ),
    (
        Category.MEMORIZATION,
        (
            "背",
            "背诵",
            "记忆",
            "默写",
            "单词",
            "memorize",
            "memorise",
            "vocabulary",
        ),
    ),
    (
        Category.READING,
        (
            "阅读",
            "读",
            "看书",
            "预习",
            "复习",
            "课件",
            "教材",
            "reading",
            "read",
            "chapter",
            "paper",
        ),
    ),
    (
        Category.PRACTICE,
        (
            "刷题",
            "做题",
            "习题",
            "真题",
            "错题",
            "试卷",
            "模拟题",
            "题库",
            "选择题",
            "大题",
            "刷",
            "practice",
            "past paper",
            "mock",
        ),
    ),
    (
        Category.PRESENTATION,
        (
            "ppt",
            "幻灯片",
            "演示文稿",
            "汇报",
            "路演",
            "slides",
            "presentation",
        ),
    ),
    (
        Category.DISCUSSION,
        (
            "讨论",
            "小组",
            "组会",
            "汇报",
            "讨论会",
            "discuss",
            "discussion",
            "group",
            "meeting",
        ),
    ),
    (
        Category.WRITING,
        (
            "写",
            "论文",
            "报告",
            "作文",
            "初稿",
            "essay",
            "writing",
            "write",
            "report",
            "thesis",
            "draft",
        ),
    ),
)

_CHINESE_CHARS = re.compile(r"(\d{3,5})\s*(?:个)?字")
_ENGLISH_WORDS = re.compile(r"(\d{2,5})\s*(?:word|words|词)", re.I)
_PAGES = re.compile(r"(\d{1,4})\s*(?:页|pages?)", re.I)
_CHAPTERS = re.compile(r"(\d{1,2})\s*(?:章|chapters?)", re.I)


class HistoryProvider(Protocol):
    """Historical actual duration lookup, implemented by T10/T14."""

    def median_minutes(self, category: Category, title: str) -> int | None:
        ...


def infer_category(task: Task) -> Category:
    """Use an explicit category or infer one from Chinese/English words."""
    if task.category is not None:
        return task.category
    text = f"{task.title} {task.description}".lower()
    for category, words in _KEYWORDS:
        if any(word in text for word in words):
            return category
    return Category.GENERAL


def estimate_minutes(
    task: Task,
    history: HistoryProvider | None = None,
) -> int:
    """Estimate duration, preferring explicit input, history, then rules."""
    category = infer_category(task)
    if task.est_minutes is not None:
        return _clamp(task.est_minutes)
    if history is not None:
        try:
            median = history.median_minutes(category, task.title)
        except Exception:
            median = None
        if median is not None and median > 0:
            return _clamp(int(median))
    return _clamp(_rule_estimate(task, category))


# Copy lengths and task words only mean something in the right category: the
# 「论文」 hint exists because *writing* one takes hours, and applying it to
# 「读一篇论文」 turned a 40-minute read into 180 minutes.
_HINTS: tuple[tuple[tuple[Category, ...] | None, str, float], ...] = (
    ((Category.WRITING,), "论文", 180.0),
    ((Category.WRITING,), "essay", 180.0),
    ((Category.WRITING,), "thesis", 180.0),
    ((Category.WRITING,), "报告", 120.0),
    ((Category.WRITING,), "report", 120.0),
    ((Category.EXPERIMENT,), "实验", 120.0),
    ((Category.EXPERIMENT,), "experiment", 120.0),
    ((Category.PRESENTATION,), "汇报", 90.0),
    ((Category.PRESENTATION,), "演示", 90.0),
    ((Category.PRESENTATION,), "presentation", 90.0),
    ((Category.PRESENTATION,), "slides", 90.0),
    ((Category.PRACTICE,), "真题", 45.0),
    ((Category.PRACTICE,), "模拟题", 45.0),
    (None, "复习", 60.0),
    (None, "review", 60.0),
    (None, "预习", 45.0),
    (None, "preview", 45.0),
)


def _rule_estimate(task: Task, category: Category) -> int:
    base = float(_CATEGORY_BASE[category])
    text = f"{task.title} {task.description}"
    lowered = text.lower()

    match = _CHINESE_CHARS.search(text)
    if match:
        chars = int(match.group(1))
        if category is Category.WRITING:
            base = max(base, chars / 1000.0 * 60.0)
        elif category is Category.READING:
            base = max(base, chars / 300.0 * 10.0)
        elif category is Category.MEMORIZATION:
            base = max(base, chars / 100.0 * 15.0)

    match = _ENGLISH_WORDS.search(text)
    if match:
        words = int(match.group(1))
        if category is Category.WRITING:
            base = max(base, words / 1000.0 * 60.0)
        elif category is Category.READING:
            base = max(base, words / 250.0 * 1.0)

    match = _PAGES.search(text)
    if match:
        base = max(base, int(match.group(1)) * 1.5)
    match = _CHAPTERS.search(text)
    if match:
        base = max(base, int(match.group(1)) * 45.0)

    for categories, keyword, minutes in _HINTS:
        if categories is not None and category not in categories:
            continue
        if keyword in lowered:
            base = max(base, minutes)
    return int(round(base / 5.0) * 5)


def _clamp(value: int) -> int:
    return max(15, min(600, int(value)))
