"""Focus verbs shared by the channel machine and the focus channel.

``skip`` / ``extend`` / ``status`` / ``split`` / ``stuck`` used to exist only in
``FocusService.control`` and only the REST endpoint could reach them, so saying
「跳过这一步」 on the device did nothing. Both callers now go through this module
so the copy and the side effects cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from channel.base import Action, Intent

# What the device says when a focus verb lands but nothing is running.
IDLE_REPLY = "现在没有在计时。说“开始专注”我就开始。"

# 「太难了」outside a timer: keep it short, offer one concrete next move, and
# never turn the sentence into a task.
COMFORT_REPLY = (
    "我在。这一步可以先不做——难的时候把步子切小就行。"
    "说“帮我安排”，我把它拆成 5 分钟的一小步。"
)

# Spoken on the first stuck signal, before actually shrinking the step.
STUCK_REPLY = "这一步比预想的难。说“换小一点”，我把它拆成 5 分钟。"

SPLIT_REPLY = "好，只做开头 5 分钟。开始了叫我。"


def is_active(focus: Any) -> bool:
    if focus is None:
        return False
    state = focus.snapshot()
    return state.get("status") in {"running", "paused"}


def remaining_text(state: dict[str, Any]) -> str:
    seconds = max(0, int(state.get("remaining_seconds") or 0))
    minutes = seconds // 60
    rest = seconds % 60
    title = str(state.get("title") or "").strip()
    if state.get("status") == "paused":
        prefix = "已暂停，"
    else:
        prefix = ""
    if minutes and rest:
        clock = f"{minutes} 分 {rest} 秒"
    elif minutes:
        clock = f"{minutes} 分钟"
    else:
        clock = f"{rest} 秒"
    tail = f"，还剩 {clock}" if prefix else f"还剩 {clock}"
    if title:
        return f"{prefix}「{title}」{tail}"
    return prefix + tail


def handle(focus: Any, intent: Intent) -> list[Action] | None:
    """Run one focus verb; ``None`` means "not mine"."""
    name = intent.name
    if name not in {"skip", "extend", "status", "split", "stuck"}:
        return None
    if not is_active(focus):
        return [Action("speak", {"text": IDLE_REPLY})]
    if name == "status":
        return [
            Action("speak", {"text": remaining_text(focus.snapshot())})
        ]
    if name == "skip":
        result = focus.control("skip")
        nxt = (result.get("state") or {}).get("title") if result else ""
        if result and result.get("ok") and nxt:
            return [Action("speak", {"text": f"跳过。接着做：{nxt}"})]
        return [Action("speak", {"text": "跳过这一步。"})]
    if name == "extend":
        minutes = int(intent.args.get("minutes") or 10)
        focus.control("extend", minutes)
        return [Action("speak", {"text": f"再给这一步 {minutes} 分钟。"})]
    if name == "split":
        result = focus.control("split")
        text = SPLIT_REPLY
        if result and not result.get("ok"):
            text = IDLE_REPLY
        return [Action("speak", {"text": text})]
    if name == "stuck":
        result = focus.control("stuck")
        split = bool(result and result.get("split"))
        return [
            Action(
                "speak",
                {"text": SPLIT_REPLY if split else STUCK_REPLY},
            )
        ]
    return None
