"""T23 optional phone app usage intake; default off and local only."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from planner.timeutil import default_tz

logger = logging.getLogger(__name__)

class UsageService:
    def __init__(
        self,
        path: str | Path,
        *,
        enabled: bool = False,
        max_packages: int = 50,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.max_packages = max(1, max_packages)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "platform": "android-only",
            "ios": (
                "iOS does not expose per-app foreground usage; "
                "use Screen Time screenshot or skip"
            ),
            "privacy": (
                "only package names and minutes; contents are never uploaded"
            ),
            "top": self.top(5),
        }

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.enabled = bool(enabled)
        self._save({"enabled": self.enabled,
                   "packages": self._load().get("packages", {})})
        return self.status()

    def ingest(self, packages: dict[str, int]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "accepted": False,
                "reason": "usage collection is disabled",
            }
        clean = {
            str(package)[:120]: max(0, int(minutes))
            for package, minutes in packages.items()
        }
        state = self._load()
        state["packages"] = {
            **state.get("packages", {}),
            **clean,
        }
        state["enabled"] = True
        state["updated_at"] = datetime.now(default_tz()).isoformat(timespec="seconds")
        self._save(state)
        return {
            "accepted": True,
            "top": self.top(5),
            "privacy": "local only",
        }

    def top(self, limit: int = 5) -> list[dict[str, Any]]:
        packages = self._load().get("packages", {})
        ranked = sorted(
            packages.items(),
            key=lambda item: int(item[1]),
            reverse=True,
        )[: max(1, limit)]
        return [
            {"package": package, "minutes": int(minutes)}
            for package, minutes in ranked
        ]

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8"))
        except Exception:
            logger.exception("usage state read failed")
            return {}

    def _save(self, state: dict[str, Any]) -> None:
        packages = state.get("packages", {})
        if len(packages) > self.max_packages:
            ranked = sorted(
                packages.items(),
                key=lambda item: int(item[1]),
                reverse=True,
            )[: self.max_packages]
            state["packages"] = dict(ranked)
        self.path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
