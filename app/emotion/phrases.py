"""T16 non-judgmental celebration phrases."""

from __future__ import annotations

import random

PHRASES = (
    "这一小步，稳稳的。",
    "你把它往前推了一点。",
    "很好，继续保持这个节奏。",
    "这一步已经算数了。",
    "谢谢你愿意开始。",
    "思路会越走越清楚的。",
    "今天的光，在这里亮了一下。",
    "先完成，再完美。",
    "你正在把大事拆小。",
    "这一页翻过去了。",
    "给自己一点掌声。",
    "这个进度值得被看见。",
    "慢一点也没关系。",
    "你做得很认真。",
    "又靠近了一点。",
    "这段专注很珍贵。",
    "现在可以歇一小会儿。",
    "你的坚持有回声。",
    "这一小步很了不起。",
    "我们把下一步留到等会儿。",
)

FORBIDDEN = ("终于", "比上周", "落后", "欠账", "拖延", "懒", "失败", "竟然")


def pick_phrase(previous: str = "", rng: random.Random | None = None) -> str:
    pool = [phrase for phrase in PHRASES if phrase != previous]
    return (rng or random).choice(pool)


def check_phrase(text: str) -> bool:
    return not any(word in text for word in FORBIDDEN)
