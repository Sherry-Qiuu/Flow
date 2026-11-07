"""Time zone helpers with a small fallback for Windows dev machines.

Raspberry Pi OS ships the IANA database. A bare Windows Python often
does not, so ``Asia/Shanghai`` falls back to a fixed UTC+8 zone. The
product only displays China Standard Time, which has no daylight saving.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CHINA_ZONES = {"asia/shanghai", "prc", "etc/gmt-8"}
_HHMM = re.compile(r"^(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)$")

# ``FLOW_TIMEZONE`` used to be validated and then ignored: a dozen modules
# froze ``Asia/Shanghai`` into a module constant at import time, so changing
# the config moved the clock on two services and nowhere else. Modules now ask
# for ``default_tz()`` at call time, and ``configure()`` is called once from
# ``create_app`` with the resolved setting.
_DEFAULT_NAME = "Asia/Shanghai"
_DEFAULT: tzinfo | None = None


def tz_for(name: str) -> tzinfo:
    key = (name or "Asia/Shanghai").strip()
    lowered = key.lower()
    if lowered in {"utc", "etc/utc", "gmt", "z"}:
        return ZoneInfo("UTC") if _has_zone("UTC") else timezone.utc
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        if lowered in _CHINA_ZONES:
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        raise ValueError(
            f"unknown time zone {name!r}; install tzdata for full IANA support"
        ) from None


def _has_zone(key: str) -> bool:
    try:
        ZoneInfo(key)
        return True
    except ZoneInfoNotFoundError:
        return False


def configure(name: str | None = None) -> tzinfo:
    """Set the process-wide display zone from ``app.timezone``."""
    global _DEFAULT_NAME, _DEFAULT
    _DEFAULT_NAME = (name or "Asia/Shanghai").strip() or "Asia/Shanghai"
    _DEFAULT = tz_for(_DEFAULT_NAME)
    return _DEFAULT


def default_tz() -> tzinfo:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = tz_for(_DEFAULT_NAME)
    return _DEFAULT


def default_tz_name() -> str:
    return _DEFAULT_NAME


def parse_hhmm(value: str) -> time:
    match = _HHMM.match(value.strip())
    if not match:
        raise ValueError(f"expected HH:MM, got {value!r}")
    return time(int(match.group("hour")), int(match.group("minute")))


def format_hhmm(value: datetime) -> str:
    return value.strftime("%H:%M")


def at(day: date, clock: time, zone: tzinfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=zone)


def ensure_aware(value: datetime, zone: tzinfo) -> datetime:
    """Treat naive input as local time; convert aware input to ``zone``."""
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def minutes_between(start: datetime, end: datetime) -> int:
    return int(round((end - start).total_seconds() / 60.0))
