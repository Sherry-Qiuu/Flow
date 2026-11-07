"""Text intent router for the six built-in tools.

The tables below are ordered, not a bag of keywords: earlier rules win, so a
sentence that merely *contains* a tool alias must not be stolen from a more
specific rule. Two rules in particular are load-bearing:

* a bare 「开始」 only starts the timer when it is the whole utterance —
  「开始写论文」 is work to plan, not a timer to start;
* a sentence about how hard something is (「太难了不想做了」) is never a task,
  even though it contains 做.
"""

from __future__ import annotations

import re
from typing import Any

from channel.base import Intent

TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "clock": ("时钟", "几点", "clock"),
    "tasks": ("任务清单", "任务", "待办", "清单", "tasks"),
    "plan": ("计划表", "计划", "安排", "plan"),
    "focus": ("专注计时器", "专注计时", "番茄钟", "计时器", "专注", "focus"),
    "reminder": ("提醒", "闹钟", "reminder"),
    "music": ("音乐", "播放器", "music"),
}

BACK_WORDS = ("返回", "回去", "退出", "回到主页", "back")

CONTROL_WORDS: dict[str, tuple[str, ...]] = {
    "start": ("开始专注", "开始计时", "启动"),
    "pause": ("暂停", "停一下"),
    "resume": ("继续", "恢复"),
    "finish": ("结束", "完成计时", "停止"),
    "done": ("完成第一条", "做完了", "完成"),
    "play": ("播放", "放音乐"),
    "next": ("下一首", "换一首"),
    "skip": ("跳过", "跳这一步", "换下一步", "换一个"),
    "extend": ("再来", "再给", "延长", "多给"),
    "status": ("还剩", "还有多久", "剩多久", "几分钟了", "还剩几分钟"),
    "split": ("换小一点", "拆小", "小一点", "简单点", "更小的一步"),
    "return": ("我回来了", "回来了", "我回座位了"),
}

CLARIFY_REPLY = "你是想专注计时还是看任务清单？"

# Only these verbs are global enough to beat a tool alias when they lead the
# sentence. "播放音乐" still belongs to the music channel; a bare "开始" is
# handled separately because it is too common a verb to own a prefix.
_LEADING_CONTROL = (
    "pause",
    "resume",
    "finish",
    "done",
    "skip",
    "extend",
    "split",
    "return",
)

# 「开始」 alone means "start the timer"; followed by anything it is a normal
# verb ("开始写论文"). Exact match only.
BARE_START = ("开始", "开始吧", "可以开始了", "begin")

# Phrases that ask for a plan rather than opening the plan list. "计划" and
# "安排" are also tool aliases, so these must be checked first.
PLAN_PHRASES = (
    "帮我安排",
    "安排一下",
    "安排今天",
    "安排明天",
    "做计划",
    "排个计划",
    "制定计划",
    "规划一下",
)

# The kiosk promise is "say one sentence, get a plan", so a bare list of
# things to do ("写论文，背50个单词") has to reach the planner instead of
# dying as "unknown". Any of these words makes the sentence a task.
TASK_VERBS = (
    "写",
    "背",
    "复习",
    "预习",
    "做",
    "读",
    "练",
    "刷",
    "整理",
    "准备",
    "交",
    "学",
    "翻译",
    "画",
    "改",
    "检查",
    "跑",
    "开会",
    "论文",
    "作业",
    "单词",
    "报告",
    "汇报",
    "实验",
    "读书",
)

# ...unless it is a question, in which case guessing a task list would be
# worse than asking again.
QUESTION_WORDS = ("吗", "什么", "怎么", "为什么", "多久", "几点", "哪", "?")

# "This is too hard / I don't want to" is a feeling, not a to-do. Without this
# guard 「太难了不想做了」 became a task named exactly that, and the planner
# then answered 「拆解《太难了不想做了》，写下 3 个完成要点」.
DISCOURAGE_WORDS = (
    "太难",
    "好难",
    "不会做",
    "做不到",
    "做不下去",
    "学不下去",
    "看不进去",
    "静不下心",
    "坚持不住",
    "没动力",
    "没心情",
    "不想做",
    "不想学",
    "不想写",
    "不想动",
    "想放弃",
    "放弃算了",
    "烦死",
    "好烦",
    "崩溃",
    "好累",
    "太累",
    "撑不住",
)

# An explicit "open / show me" outranks the feeling guard: 「太难了，打开任务
# 清单」 is still a request for the list.
_EXPLICIT_OPEN = ("打开", "看下", "看看", "切换到", "回到")

# Saying you want to focus is a request to start, not to look at the timer
# (README: 「我要专注 25 分钟」 hands over a running timer).
FOCUS_START_PHRASES = (
    "我要专注",
    "我想专注",
    "想专注",
    "来个专注",
    "专注一下",
    "开始专注",
    "开始计时",
)

_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_SPECIAL_MINUTES = {"半小时": 30, "半个小时": 30, "一刻钟": 15, "一小时": 60}


def route(text: str, *, source: str = "voice") -> Intent:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return Intent(name="unknown", text=normalized, source=source)
    lowered = normalized.lower()

    if lowered in BARE_START or lowered.rstrip("。！!~") in BARE_START:
        return Intent(name="start", text=normalized, source=source)

    for phrase in FOCUS_START_PHRASES:
        if lowered.startswith(phrase):
            args: dict[str, Any] = {"open_focus": True}
            args.update(_tool_args("focus", normalized))
            return Intent(
                name="start",
                text=normalized,
                source=source,
                args=args,
                confidence=0.85,
            )

    if any(word in lowered for word in DISCOURAGE_WORDS) and not any(
        word in lowered for word in _EXPLICIT_OPEN
    ):
        return Intent(
            name="discourage",
            text=normalized,
            source=source,
            confidence=0.7,
        )

    for phrase in PLAN_PHRASES:
        if phrase in lowered:
            return Intent(
                name="make_plan",
                text=normalized,
                source=source,
                confidence=0.8,
            )

    # A leading control verb wins over a tool alias: "结束" means stop the
    # step, not open a channel that happens to be called that.
    for name in _LEADING_CONTROL:
        for word in CONTROL_WORDS[name]:
            if lowered.startswith(word):
                return Intent(
                    name=name,
                    text=normalized,
                    source=source,
                    args=_verb_args(name, normalized),
                )

    for tool, aliases in TOOL_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                return Intent(
                    name="open_tool",
                    text=normalized,
                    source=source,
                    tool=tool,
                    args=_tool_args(tool, normalized),
                    confidence=0.9,
                )

    if any(word in lowered for word in BACK_WORDS):
        return Intent(name="back", text=normalized, source=source)
    for name, words in CONTROL_WORDS.items():
        if any(word in lowered for word in words):
            return Intent(
                name=name,
                text=normalized,
                source=source,
                args=_verb_args(name, normalized),
            )
    if any(word in lowered for word in ("打开", "切换", "那个")):
        return Intent(
            name="clarify",
            text=normalized,
            source=source,
            args={"reply": CLARIFY_REPLY},
            confidence=0.4,
        )
    if _looks_like_work(lowered):
        return Intent(
            name="make_plan",
            text=normalized,
            source=source,
            confidence=0.6,
        )
    return Intent(name="unknown", text=normalized, source=source)


def _looks_like_work(lowered: str) -> bool:
    if any(word in lowered for word in QUESTION_WORDS):
        return False
    if not any(word in lowered for word in TASK_VERBS):
        return False
    # 「复习」 or 「背单词」 alone is a subject, not a finished task; asking for
    # one more detail beats planning something the user cannot recognise.
    stripped = re.sub(r"[，,。.\s]+", "", lowered)
    return len(stripped) >= 3


def _verb_args(name: str, text: str) -> dict[str, Any]:
    if name == "extend":
        minutes = _minutes_in(text)
        return {"minutes": minutes} if minutes else {}
    if name == "skip":
        return {}
    return {}


def _tool_args(tool: str, text: str) -> dict[str, Any]:
    if tool != "focus":
        return {}
    minutes = _minutes_in(text)
    return {"minutes": minutes} if minutes else {}


def _minutes_in(text: str) -> int | None:
    lowered = text.lower()
    match = re.search(r"(\d{1,3})\s*(?:分钟|min)", lowered)
    if match:
        return max(1, min(180, int(match.group(1))))
    for phrase, value in _SPECIAL_MINUTES.items():
        if phrase in text:
            return value
    match = re.search(
        r"([一二两三四五六七八九十]{1,3})\s*分钟",
        text,
    )
    if match:
        value = _cn_minutes(match.group(1))
        if value:
            return max(1, min(180, value))
    return None


def _cn_minutes(value: str) -> int | None:
    if value in _CN_DIGITS:
        return _CN_DIGITS[value]
    if value.startswith("十"):
        rest = _CN_DIGITS.get(value[1:], 0)
        return 10 + rest if rest is not None else None
    if "十" in value:
        tens, _, ones = value.partition("十")
        if tens in _CN_DIGITS and (ones == "" or ones in _CN_DIGITS):
            return _CN_DIGITS[tens] * 10 + (_CN_DIGITS.get(ones, 0))
    return None
