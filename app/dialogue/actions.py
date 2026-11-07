"""T08 action union and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class DialogueAction:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "payload": dict(self.payload)}


class ActionHandler(Protocol):
    def __call__(self, action: DialogueAction) -> dict[str, Any]:
        ...


class DialogueDispatcher:
    def __init__(
        self,
        *,
        on_channel: Callable[[str], Any] | None = None,
        on_create_task: Callable[[dict], Any] | None = None,
        on_update_task: Callable[[dict], Any] | None = None,
        on_delete_task: Callable[[dict], Any] | None = None,
        on_plan: Callable[[str, dict], Any] | None = None,
        on_confirm: Callable[[dict], Any] | None = None,
        on_cancel: Callable[[dict], Any] | None = None,
        on_query: Callable[[dict], Any] | None = None,
        on_ask: Callable[[dict], Any] | None = None,
    ) -> None:
        self.on_channel = on_channel
        self.on_create_task = on_create_task
        self.on_update_task = on_update_task
        self.on_delete_task = on_delete_task
        self.on_plan = on_plan
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.on_query = on_query
        self.on_ask = on_ask

    def dispatch(self, actions: list[DialogueAction]) -> list[dict[str, Any]]:
        results = []
        for action in actions:
            callback = {
                "enter_channel": self.on_channel,
                "create_task": self.on_create_task,
                "update_task": self.on_update_task,
                "delete_task": self.on_delete_task,
                "build_plan": lambda payload: self.on_plan(
                    "build", payload
                ),
                "modify_plan": lambda payload: self.on_plan(
                    "modify", payload
                ),
                "confirm": self.on_confirm,
                "cancel": self.on_cancel,
                "query": self.on_query,
                "ask": self.on_ask,
            }.get(action.kind)
            if callback is None:
                results.append({"kind": action.kind, "ok": False})
                continue
            try:
                result = callback(action.payload)
                results.append(
                    {"kind": action.kind, "ok": True, "result": result}
                )
            except Exception as exc:
                results.append(
                    {"kind": action.kind, "ok": False, "error": str(exc)}
                )
        return results
