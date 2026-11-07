"""T11 draft commit, duplicate detection and camera capture service."""

from __future__ import annotations

import logging
from typing import Any

from bus import topics
from capture.extract import TaskDraft, dedupe_drafts, extract_from_text
from capture.photo import PhotoImporter
from data.repositories import Repositories
from planner.models import Task

logger = logging.getLogger(__name__)


class TaskCaptureService:
    def __init__(
        self,
        repos: Repositories,
        *,
        publisher: Any = None,
        camera: Any = None,
        inbox: str = "data/inbox",
    ) -> None:
        self.repos = repos
        self.publisher = publisher
        self.photo = PhotoImporter(camera, inbox=inbox) if camera else None
        self._recent: set[str] = set()

    def from_text(self, text: str, *, source: str = "text") -> list[dict]:
        drafts = extract_from_text(text, source=source)
        existing = {
            _key(task.title) for task in self.repos.tasks.list()
        } | self._recent
        drafts = dedupe_drafts(drafts, existing)
        self._recent.update(_key(draft.title) for draft in drafts)
        return [draft.to_dict() for draft in drafts]

    def photo_drafts(self, jpeg: bytes) -> list[dict]:
        if self.photo is None:
            return []
        drafts = dedupe_drafts(self.photo.extract(jpeg))
        return [draft.to_dict() for draft in drafts]

    def capture_photo(self) -> dict[str, Any]:
        if self.photo is None:
            return {"ok": False, "reason": "no camera"}
        result = self.photo.capture()
        if result.get("ok"):
            existing = {
                _key(task.title) for task in self.repos.tasks.list()
            }
            parsed = [
                _draft(item)
                for item in result.get("drafts", [])
            ]
            parsed = dedupe_drafts(parsed, existing)
            result["drafts"] = [draft.to_dict() for draft in parsed]
        return result

    def commit(
        self,
        drafts: list[dict] | list[TaskDraft],
    ) -> list[Task]:
        tasks: list[Task] = []
        existing = {
            _key(task.title) for task in self.repos.tasks.list()
        }
        for raw in drafts:
            draft = raw if isinstance(raw, TaskDraft) else _draft(raw)
            if not draft.selected or not draft.title.strip():
                continue
            if _key(draft.title) in existing:
                continue
            task = Task(
                id=f"t_{__import__('uuid').uuid4().hex[:12]}",
                title=draft.title,
                description=draft.quote,
                est_minutes=draft.est_minutes,
                deadline=draft.deadline,
                priority=2 if draft.priority == "high" else 3,
                source=draft.source,
            )
            self.repos.tasks.create(task)
            tasks.append(task)
            existing.add(_key(task.title))
            self._publish(
                topics.TASK_CREATED,
                {
                    "task_id": task.id,
                    "title": task.title,
                    "source": task.source,
                },
            )
        return tasks

    def _publish(self, topic: str, payload: dict) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("capture publish failed: %s", topic)


def _draft(raw: dict) -> TaskDraft:
    from datetime import datetime

    deadline = raw.get("deadline")
    parsed = None
    if deadline:
        try:
            parsed = datetime.fromisoformat(str(deadline))
        except ValueError:
            parsed = None
    return TaskDraft(
        title=str(raw.get("title", "")),
        deadline=parsed,
        est_minutes=raw.get("est_minutes"),
        course=raw.get("course"),
        priority=str(raw.get("priority", "normal")),
        source=str(raw.get("source", "text")),
        quote=str(raw.get("quote", "")),
        selected=bool(raw.get("selected", True)),
    )


def _key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())
