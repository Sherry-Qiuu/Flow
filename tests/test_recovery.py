"""T29 recovery report test."""

from __future__ import annotations

import json
from pathlib import Path

from recovery import RecoveryReport


def test_recovery_snapshot(workspace_tmp):
    data = workspace_tmp / "recovery-data"
    data.mkdir(exist_ok=True)
    (data / "backup").mkdir(exist_ok=True)
    (data / "focus_state.json").write_text(
        json.dumps(
            {
                "plan_id": "p1",
                "item_id": "p1_i0",
                "status": "running",
            }
        ),
        encoding="utf-8",
    )
    (data / "backup" / "flow-1.db").write_bytes(b"x")
    report = RecoveryReport(data).snapshot()
    assert report["resume_step"] == "p1_i0"
    assert report["backup_count"] == 1
    assert report["resume_status"] == "running"
