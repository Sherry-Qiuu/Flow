"""T22 phone-to-device inbox with safe filenames and metadata."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from bus import topics

logger = logging.getLogger(__name__)
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".md"}
MAX_BYTES = 20 * 1024 * 1024


class InboxError(ValueError):
    pass


class FileInbox:
    def __init__(
        self,
        root: str | Path,
        *,
        publisher: Any = None,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.publisher = publisher
        self.max_bytes = max_bytes
        self.index_path = self.root / "inbox.json"

    def save(self, filename: str, data: bytes) -> dict[str, Any]:
        if not data:
            raise InboxError("empty file")
        if len(data) > self.max_bytes:
            raise InboxError("file exceeds 20 MB")
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXT:
            raise InboxError("file type is not allowed")
        safe_stem = re.sub(
            r"[^A-Za-z0-9_\-\u4e00-\u9fff]+",
            "-",
            Path(filename).stem,
        ).strip("-")[:48] or "upload"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.root / \
            f"{stamp}-{uuid.uuid4().hex[:8]}-{safe_stem}{suffix}"
        target.write_bytes(data)
        record = {
            "name": target.name,
            "original": Path(filename).name,
            "bytes": len(data),
            "at": datetime.now().isoformat(timespec="seconds"),
            "status": "pending",
        }
        self._append_index(record)
        self._publish(
            topics.INBOX_FILE,
            {**record, "path": str(target)},
        )
        return {"ok": True, **record, "path": str(target)}

    def list(self) -> list[dict[str, Any]]:
        if not self.index_path.is_file():
            return []
        try:
            return json.loads(self.index_path.read_text("utf-8"))
        except Exception:
            logger.exception("inbox index read failed")
            return []

    def mark(self, name: str, status: str) -> None:
        items = self.list()
        for item in items:
            if item.get("name") == name:
                item["status"] = status
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _append_index(self, record: dict[str, Any]) -> None:
        items = self.list()
        items.append(record)
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("inbox publish failed")
