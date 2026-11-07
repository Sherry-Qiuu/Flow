"""T27 weekly cards and text export."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics.collector import AnalyticsService
from analytics.distraction import DistractionService, check_tone
from data.repositories import Repositories

logger = logging.getLogger(__name__)


class WeeklyReportService:
    def __init__(
        self,
        repos: Repositories,
        analytics: AnalyticsService,
        *,
        distractions: DistractionService | None = None,
        export_dir: str | Path = "data/exports",
    ) -> None:
        self.repos = repos
        self.analytics = analytics
        self.distractions = distractions
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, days: int = 7) -> dict[str, Any]:
        metrics = self.analytics.metrics(days)
        distraction = (
            self.distractions.insights(days)
            if self.distractions is not None
            else {"count": 0, "total_minutes": 0, "peak_hours": []}
        )
        cards = []
        if metrics["events"] == 0 and distraction["count"] == 0:
            cards = [
                {
                    "title": "这周你先歇了歇",
                    "value": "慢慢来",
                    "text": "下周可以从一件小事开始。",
                },
                {
                    "title": "照顾自己也算进度",
                    "value": "0",
                    "text": "没有数据不等于没有价值。",
                },
                {
                    "title": "下周的小实验",
                    "value": "1",
                    "text": "只选一件 10 分钟能做完的事。",
                },
            ]
        else:
            cards = [
                {
                    "title": "这周你完成的小步",
                    "value": str(
                        self._count_events("step.completed", days)
                    ),
                    "text": "每一步都算数。",
                },
                {
                    "title": "最专注的时段",
                    "value": (
                        f"{distraction['peak_hours'][0]}:00"
                        if distraction["peak_hours"]
                        else "还没固定"
                    ),
                    "text": "可以把这个时段留给重要的事。",
                },
                {
                    "title": "下周的小实验",
                    "value": str(max(1, metrics["streak_days"])),
                    "text": "每天三个小步，就很好。",
                },
            ]
        payload = {
            "range_days": days,
            "cards": cards,
            "metrics": metrics,
            "distraction": distraction,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        payload["export"] = str(self.export(payload))
        return payload

    def export(self, report: dict[str, Any]) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.export_dir / f"weekly-{stamp}.txt"
        lines = ["心流周报", ""]
        for card in report["cards"]:
            lines.extend(
                [
                    f"{card['title']}：{card['value']}",
                    card["text"],
                    "",
                ]
            )
        text = "\n".join(lines)
        if not check_tone(text):
            text = "这周你完成了一些小步，下一步可以从一件小事开始。"
        path.write_text(text, encoding="utf-8")
        return path

    def _count_events(self, event: str, days: int) -> int:
        metrics = self.analytics.metrics(days)
        if event == "step.completed":
            return round(
                metrics["completion_rate"]
                * metrics["events"]
            )
        return 0
