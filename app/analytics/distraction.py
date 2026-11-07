"""T18 distraction admissions and non-judgmental insights."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from bus import topics
from data.repositories import Repositories
from planner.timeutil import tz_for

logger = logging.getLogger(__name__)
TZ = tz_for("Asia/Shanghai")

FORBIDDEN = ("又", "竟然", "居然", "拖延", "懒", "失败", "落后", "欠账")


class DistractionService:
    def __init__(self, repos: Repositories, *, publisher: Any = None) -> None:
        self.repos = repos
        self.publisher = publisher

    def log(
        self,
        *,
        minutes: int = 0,
        purpose: str = "unknown",
        context: str = "",
        source: str = "voice",
        note: str = "",
    ) -> dict[str, Any]:
        event_id = self.repos.distractions.add(
            "phone",
            note,
            minutes=minutes,
            purpose=purpose,
            context=context,
            source=source,
        )
        payload = {
            "id": event_id,
            "minutes": minutes,
            "purpose": purpose,
            "context": context,
            "source": source,
        }
        self._publish(topics.DISTRACTION_LOGGED, payload)
        return payload

    def insights(self, days: int = 7) -> dict[str, Any]:
        days = max(1, min(90, days))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = [
            row
            for row in self.repos.distractions.list(limit=5000)
            if _parse(row.get("created_at")) >= cutoff
        ]
        hours = Counter()
        contexts = Counter()
        total_minutes = 0
        for row in rows:
            created = _parse(row.get("created_at")).astimezone(TZ)
            hours[created.hour] += 1
            contexts[row.get("context") or "不清楚"] += 1
            total_minutes += int(row.get("minutes") or 0)
        return {
            "range_days": days,
            "count": len(rows),
            "total_minutes": total_minutes,
            "peak_hours": [hour for hour, _ in hours.most_common(3)],
            "top_contexts": [
                {"context": name, "count": count}
                for name, count in contexts.most_common(3)
            ],
            "avg_recovery_min": round(total_minutes / len(rows), 1)
            if rows
            else 0,
        }

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(topic, payload)
        except Exception:
            logger.exception("distraction publish failed")


def check_tone(text: str) -> bool:
    return not any(word in text for word in FORBIDDEN)


def _parse(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
