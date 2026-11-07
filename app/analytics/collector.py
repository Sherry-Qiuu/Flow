"""T26 local event collector and metric rollup."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from analytics.events import ALLOWED
from bus import topics
from data.repositories import Repositories
from planner.timeutil import default_tz

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(
        self,
        repos: Repositories,
        *,
        publisher: Any = None,
        enabled: bool = True,
    ) -> None:
        self.repos = repos
        self.publisher = publisher
        self.enabled = enabled

    def record(
        self,
        event: str,
        props: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        if event not in ALLOWED:
            raise ValueError(f"event is not whitelisted: {event}")
        event_id = self.repos.device_events.add(event, props or {})
        self._publish(event, props or {})
        return event_id

    def metrics(self, days: int = 7) -> dict[str, Any]:
        days = max(1, min(90, days))
        since = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        rows = self.repos.device_events.list(since=since, limit=5000)
        by_type: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            payload = {}
            try:
                payload = json.loads(row.get("payload_json") or "{}")
            except Exception:
                pass
            by_type.setdefault(row["type"], []).append(payload)
        completed = len(by_type.get("step.completed", []))
        skipped = len(by_type.get("step.skipped", []))
        total_steps = completed + skipped
        completion_rate = completed / total_steps if total_steps else 0.0
        actual_minutes = [
            float(item.get("actual_min", 0))
            for item in by_type.get("step.completed", [])
            if item.get("actual_min")
        ]
        distractions = self.repos.distractions.list(limit=1000)
        rest_offered = len(by_type.get("rest.offered", []))
        rest_accepted = len(by_type.get("rest.accepted", []))
        companion = self.repos.companion.get()
        streak = 0
        if companion.get("state_json"):
            try:
                streak = int(
                    json.loads(companion["state_json"]).get("streak", 0)
                )
            except Exception:
                streak = 0
        return {
            "range_days": days,
            "completion_rate": round(completion_rate, 3),
            "on_time_rate": round(_on_time_rate(rows), 3),
            "avg_step_min": round(
                sum(actual_minutes) / len(actual_minutes), 1
            )
            if actual_minutes
            else 0,
            "distractions_per_week": round(
                len(distractions) * 7 / days, 1
            ),
            "rest_accept_rate": round(
                rest_accepted / rest_offered, 3
            )
            if rest_offered
            else 0.0,
            "streak_days": streak,
            "events": len(rows),
        }

    def rollup(self, day: date | None = None) -> dict[str, Any]:
        target = day or date.today()
        metrics = self.metrics(1)
        metrics["date"] = target.isoformat()
        self.repos.metrics.upsert(target, metrics)
        return metrics

    def _publish(self, event: str, props: dict[str, Any]) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(
                "analytics.event",
                {"event": event, "props": props},
            )
        except Exception:
            logger.exception("analytics publish failed")


def _on_time_rate(rows: list[dict[str, Any]]) -> float:
    relevant = []
    for row in rows:
        if row.get("type") not in {
            "step.completed",
            "phone.contract.ended",
        }:
            continue
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except Exception:
            payload = {}
        if "on_time" in payload:
            relevant.append(bool(payload["on_time"]))
    return sum(relevant) / len(relevant) if relevant else 0.0
