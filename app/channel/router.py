"""Text intent router for the six built-in tools."""

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
    "start": ("开始专注", "开始计时", "开始", "启动"),
    "pause": ("暂停", "停一下"),
    "resume": ("继续", "恢复"),
    "finish": ("结束", "完成计时", "停止"),
    "done": ("完成第一条", "做完了", "完成"),
    "play": ("播放", "放音乐"),
    "next": ("下一首", "换一首"),
}
CLARIFY_REPLY = "你是想专注计时还是看任务清单？"


def route(text: str, *, source: str = "voice") -> Intent:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return Intent(name="unknown", text=normalized, source=source)
    lowered = normalized.lower()

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
            return Intent(name=name, text=normalized, source=source)
    if any(word in lowered for word in ("打开", "切换", "那个")):
        return Intent(
            name="clarify",
            text=normalized,
            source=source,
            args={"reply": CLARIFY_REPLY},
            confidence=0.4,
        )
    return Intent(name="unknown", text=normalized, source=source)


def _tool_args(tool: str, text: str) -> dict[str, Any]:
    if tool != "focus":
        return {}
    match = re.search(r"(\d{1,3})\s*(?:分钟|min)", text.lower())
    if match:
        return {"minutes": max(1, min(180, int(match.group(1))))}
    return {}
