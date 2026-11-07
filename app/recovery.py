"""T29 recovery report: what will be restored after a crash."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecoveryReport:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def snapshot(self) -> dict[str, Any]:
        focus_path = self.data_dir / "focus_state.json"
        focus = None
        if focus_path.is_file():
            try:
                focus = json.loads(focus_path.read_text("utf-8"))
            except Exception:
                focus = {"error": "focus state is unreadable"}
        backups = sorted(
            (self.data_dir / "backup").glob("flow-*.db")
        )
        return {
            "focus": focus,
            "last_backup": str(backups[-1]) if backups else None,
            "backup_count": len(backups),
            "resume_step": (focus or {}).get("item_id"),
            "resume_status": (focus or {}).get("status"),
            "user_message": "重启后会回到刚才那一步",
        }
