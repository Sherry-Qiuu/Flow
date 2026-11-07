"""T15 reminder specifications and next-fire calculation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from planner.timeutil import default_tz, tz_for

KINDS = ("at", "daily", "weekly", "every", "event")
WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6,
            "天": 6}


@dataclass(frozen=True)
class ReminderSpec:
    kind: str
    at: str = ""
    minutes: int = 0
    weekday: int = -1
    on: str = ""
    template: str = ""
    allow_quiet: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown reminder kind: {self.kind}")
        if not self.template.strip():
            raise ValueError("reminder template is required")
        if self.kind in {"at", "daily"} and not self.at:
            raise ValueError(f"{self.kind} requires at")
        if self.kind == "weekly" and not 0 <= self.weekday <= 6:
            raise ValueError("weekly requires weekday 0..6")
        if self.kind == "every" and self.minutes <= 0:
            raise ValueError("every requires positive minutes")
        if self.kind == "event" and not self.on:
            raise ValueError("event requires on")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at,
            "minutes": self.minutes,
            "weekday": self.weekday,
            "on": self.on,
            "template": self.template,
            "allow_quiet": self.allow_quiet,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReminderSpec":
        return cls(
            kind=str(value.get("kind") or value.get("type") or ""),
            at=str(value.get("at", "")),
            minutes=int(value.get("minutes", 0)),
            weekday=int(value.get("weekday", -1)),
            on=str(value.get("on", "")),
            template=str(value.get("template", "")),
            allow_quiet=bool(value.get("allow_quiet", False)),
            meta=dict(value.get("meta", {})),
        )

    def next_after(
        self,
        now: datetime,
        last_fired: datetime | None = None,
    ) -> str | None:
        """Return UTC ISO next fire time, or None for one-shot/event."""
        local = now.astimezone(default_tz())
        if self.kind == "at":
            target = _parse_local(self.at)
            return None if target <= local else _utc(target)
        if self.kind == "daily":
            parsed = _parse_clock(self.at)
            target = datetime.combine(local.date(), parsed, tzinfo=default_tz())
            if target <= local:
                target += timedelta(days=1)
            return _utc(target)
        if self.kind == "weekly":
            parsed = _parse_clock(self.at)
            days = (self.weekday - local.weekday()) % 7
            target = datetime.combine(local.date(), parsed, tzinfo=default_tz())
            target += timedelta(days=days)
            if target <= local:
                target += timedelta(days=7)
            return _utc(target)
        if self.kind == "every":
            base = last_fired or local
            target = base + timedelta(minutes=self.minutes)
            return _utc(target.astimezone(default_tz()))
        return None


def parse_reminder_text(
    text: str,
    now: datetime | None = None,
) -> ReminderSpec:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        raise ValueError("empty reminder text")
    moment = (now or datetime.now(default_tz())).astimezone(default_tz())
    template = raw
    for prefix in ("提醒我", "提醒", "记得"):
        if prefix in template:
            template = template.split(prefix, 1)[1].strip()
            break
    if not template:
        template = raw

    daily = re.search(r"每天\s*(\d{1,2})(?:[:：点](\d{1,2})?)?", raw)
    if daily:
        hour = int(daily.group(1))
        minute = int(daily.group(2) or 0)
        return ReminderSpec(
            kind="daily",
            at=f"{hour:02d}:{minute:02d}",
            template=template,
        )
    weekly = re.search(
        r"每周([一二三四五六日天])\s*(\d{1,2})(?:[:：点](\d{1,2})?)?",
        raw,
    )
    if weekly:
        return ReminderSpec(
            kind="weekly",
            weekday=WEEKDAYS[weekly.group(1)],
            at=f"{int(weekly.group(2)):02d}:{int(weekly.group(3) or 0):02d}",
            template=template,
        )
    every = re.search(r"每\s*(\d{1,3})\s*分钟", raw)
    if every:
        return ReminderSpec(
            kind="every",
            minutes=max(1, int(every.group(1))),
            template=template,
        )
    relative = re.search(r"(\d{1,3})\s*分钟后", raw)
    if relative:
        target = moment + timedelta(minutes=int(relative.group(1)))
        return ReminderSpec(
            kind="at",
            at=target.isoformat(),
            template=template,
        )
    at_clock = re.search(r"(\d{1,2})[:：点](\d{1,2})?", raw)
    if at_clock:
        hour = int(at_clock.group(1))
        minute = int(at_clock.group(2) or 0)
        target = datetime.combine(
            moment.date(),
            time(hour, minute),
            tzinfo=default_tz(),
        )
        if target <= moment:
            target += timedelta(days=1)
        return ReminderSpec(
            kind="at",
            at=target.isoformat(),
            template=template,
        )
    raise ValueError("could not parse reminder time")


def _parse_local(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz())
    return parsed.astimezone(default_tz())


def _parse_clock(value: str) -> time:
    hour, _, minute = value.partition(":")
    return time(int(hour), int(minute or 0))


def _utc(value: datetime) -> str:
    return value.astimezone(tz_for("UTC")).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
