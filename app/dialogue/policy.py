"""T08 deterministic multi-turn policy (LLM adapter can replace later)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from capture.extract import _parse_deadline, extract_from_text
from channel.router import route
from dialogue.actions import DialogueAction
from dialogue.context import DialogueContext
from dialogue.tools import TOOL_NAMES
from planner.timeutil import default_tz

DESTRUCTIVE = ("删除", "删掉", "清空", "覆盖", "重置")
YES = ("确认", "是", "好", "对", "可以", "删除")
NO = ("取消", "不", "算了", "别")


class Dialogue:
    def __init__(self, *, now_fn=None) -> None:
        self.context = DialogueContext()
        self.now_fn = now_fn or (lambda: datetime.now(default_tz()))
        self._last_actions: list[DialogueAction] = []

    def turn(
        self,
        text: str,
        *,
        source: str = "voice",
    ) -> list[DialogueAction]:
        text = " ".join(str(text or "").strip().split())
        if not text:
            return []
        self.context.expire_if_needed()
        self.context.add("user", text, source)
        if self.context.pending:
            handled = self._handle_pending(text)
            if handled is not None:
                self._record_actions(handled)
                return handled
        segments = [
            part.strip()
            for part in re.split(r"然后|并且|接着", text)
            if part.strip()
        ]
        actions: list[DialogueAction] = []
        for segment in segments:
            actions.extend(self._one(segment, source))
        self._record_actions(actions)
        return actions

    def _one(self, text: str, source: str) -> list[DialogueAction]:
        if any(word in text for word in DESTRUCTIVE):
            if "第二个" in text:
                return self._confirm(
                    "delete_task",
                    {"index": 2, "text": text},
                    "确认要删除第二个任务吗？",
                )
            return self._confirm(
                "delete_task",
                {"text": text},
                "这个操作会改变已有数据，确认要这样做吗？",
            )
        if any(word in text for word in ("打开", "切换", "看下", "看看")):
            intent = route(text, source=source)
            if intent.name == "open_tool" and intent.tool:
                self.context.channel = intent.tool
                return [
                    DialogueAction(
                        "enter_channel",
                        {"tool": intent.tool, "text": text},
                    )
                ]
        if any(word in text for word in ("生成计划", "安排一下", "排个计划")):
            return [DialogueAction("build_plan", {"text": text})]
        if "改成" in text and self.context.task_draft is not None:
            deadline = _parse_deadline(text, self.now_fn())
            if deadline is not None:
                self.context.task_draft["deadline"] = deadline.isoformat()
                return [
                    DialogueAction(
                        "update_task",
                        {
                            "field": "deadline",
                            "value": deadline.isoformat(),
                            "draft": self.context.task_draft,
                        },
                    )
                ]
        if text.startswith("提醒我"):
            title = text.removeprefix("提醒我").strip() or "休息一下"
            draft = {
                "title": title,
                "source": "voice",
                "quote": text,
                "selected": True,
            }
            self.context.task_draft = draft
            return [DialogueAction("create_task", {"draft": draft})]
        drafts = extract_from_text(text, now=self.now_fn(), source=source)
        if drafts:
            first = drafts[0].to_dict()
            self.context.task_draft = first
            if first.get("deadline") is None:
                self.context.pending = {
                    "kind": "await_deadline",
                    "draft": first,
                }
                return [
                    DialogueAction(
                        "ask",
                        {"text": "这件事的截止时间是什么时候？"},
                    )
                ]
            return [
                DialogueAction(
                    "create_task",
                    {
                        "draft": draft.to_dict(),
                        "count": len(drafts),
                    },
                )
                for draft in drafts
            ]
        if "什么" in text or "多少" in text or "看看" in text:
            return [DialogueAction("query", {"text": text})]
        return [
            DialogueAction(
                "ask",
                {"text": "你是想创建一个任务，还是打开某个工具？"},
            )
        ]

    def _handle_pending(self, text: str) -> list[DialogueAction] | None:
        pending = self.context.pending or {}
        if pending.get("kind") == "await_deadline":
            deadline = _parse_deadline(text, self.now_fn())
            if deadline is not None:
                draft = pending.get("draft", {})
                draft["deadline"] = deadline.isoformat()
                self.context.pending = None
                self.context.task_draft = draft
                return [
                    DialogueAction(
                        "update_task",
                        {
                            "field": "deadline",
                            "value": deadline.isoformat(),
                            "draft": draft,
                        },
                    )
                ]
            return None
        if str(pending.get("kind", "")).startswith("confirm_"):
            if any(word in text for word in NO):
                self.context.pending = None
                return [DialogueAction("cancel", {"reason": "user_cancelled"})]
            if any(word in text for word in YES):
                kind = str(pending.get("kind")).removeprefix("confirm_")
                payload = pending.get("payload", {})
                self.context.pending = None
                return [DialogueAction(kind, payload)]
            self.context.pending = None
            return None
        return None

    def _confirm(
        self,
        kind: str,
        payload: dict[str, Any],
        question: str,
    ) -> list[DialogueAction]:
        self.context.pending = {
            "kind": f"confirm_{kind}",
            "payload": payload,
            "question": question,
        }
        return [DialogueAction("ask", {"text": question})]

    def _record_actions(self, actions: list[DialogueAction]) -> None:
        self._last_actions = actions
        for action in actions:
            self.context.add(
                "assistant",
                action.payload.get("text", action.kind),
            )

    def summary(self) -> dict[str, Any]:
        return {
            **self.context.summary(),
            "tools": list(TOOL_NAMES),
        }
