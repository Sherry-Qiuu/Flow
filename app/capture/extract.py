"""T11 task drafts and rule-based text extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from planner.timeutil import default_tz

_WEEKDAYS = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
_COURSES = (
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "编程",
    "论文",
    "实验",
)

# "帮我安排今天" asks for a plan; it must not become a task called 「安排」.
_SCHEDULE_ONLY = frozenset(
    {
        "安排",
        "安排一下",
        "帮我安排",
        "做计划",
        "排个计划",
        "制定计划",
        "规划",
        "规划一下",
        "计划",
        "计划一下",
        "日程",
        "排一下",
    }
)


@dataclass(frozen=True)
class TaskDraft:
    title: str
    deadline: datetime | None = None
    est_minutes: int | None = None
    course: str | None = None
    priority: str = "normal"
    source: str = "text"
    quote: str = ""
    selected: bool = True
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "est_minutes": self.est_minutes,
            "course": self.course,
            "priority": self.priority,
            "source": self.source,
            "quote": self.quote,
            "selected": self.selected,
            "duplicate": self.duplicate,
        }


def extract_from_text(
    text: str,
    *,
    now: datetime | None = None,
    source: str = "text",
) -> list[TaskDraft]:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return []
    moment = (now or datetime.now(default_tz())).astimezone(default_tz())
    segments = _segments(raw)
    drafts = []
    for segment in segments:
        deadline = _parse_deadline(segment, moment)
        duration = _parse_duration(segment)
        course = next((item for item in _COURSES if item in segment), None)
        priority = (
            "high"
            if any(word in segment for word in ("紧急", "截止", "明天", "后天"))
            else "normal"
        )
        title = _clean_title(segment)
        # A one-character title is a fragment of the previous sentence
        # ("写论文，明天交" -> 「交」), never something to plan.
        if len(title) < 2:
            continue
        if _normalize(title) not in _SCHEDULE_ONLY:
            drafts.append(
                TaskDraft(
                    title=title,
                    deadline=deadline,
                    est_minutes=duration,
                    course=course,
                    priority=priority,
                    source=source,
                    quote=segment,
                )
            )
    return drafts


def _segments(raw: str) -> list[str]:
    """Split spoken text into tasks.

    Spoken lists use commas as much as they use 「然后」, so a comma ends a
    task — unless the fragment after it is only a time, which belongs to the
    task before: 「背50个单词，明天」 is one task with a deadline.
    """
    parts = [
        part.strip(" ，。；;")
        for part in re.split(r"然后|接着|；|;|。|\n|，|,", raw)
    ]
    merged: list[str] = []
    for part in parts:
        if not part:
            continue
        if merged and _is_time_only(part.replace(" ", "")):
            merged[-1] = f"{merged[-1]}{part}"
            continue
        merged.append(part)
    return merged


def dedupe_drafts(
    drafts: list[TaskDraft],
    existing_titles: set[str] | None = None,
) -> list[TaskDraft]:
    existing = existing_titles or set()
    result = []
    seen = set()
    for draft in drafts:
        key = _normalize(draft.title)
        duplicate = key in existing or key in seen
        result.append(
            TaskDraft(
                title=draft.title,
                deadline=draft.deadline,
                est_minutes=draft.est_minutes,
                course=draft.course,
                priority=draft.priority,
                source=draft.source,
                quote=draft.quote,
                selected=draft.selected,
                duplicate=duplicate,
            )
        )
        seen.add(key)
    return result


def _parse_deadline(text: str, now: datetime) -> datetime | None:
    day = None
    if "后天" in text:
        day = now.date() + timedelta(days=2)
    elif "明天" in text:
        day = now.date() + timedelta(days=1)
    elif "今天" in text or "今晚" in text:
        day = now.date()
    else:
        month_day = re.search(r"(\d{1,2})\s*[月\-/]\s*(\d{1,2})", text)
        if month_day:
            try:
                day = now.replace(
                    month=int(month_day.group(1)),
                    day=int(month_day.group(2)),
                ).date()
            except ValueError:
                day = None
        else:
            weekday = re.search(r"(下周|周|星期)([一二三四五六日天])", text)
            if weekday:
                target = _WEEKDAYS[weekday.group(2)]
                delta = (target - now.weekday()) % 7
                if weekday.group(1) == "下周":
                    delta += 7
                day = now.date() + timedelta(days=delta)
    relative = re.search(r"(\d{1,3})\s*(分钟|小时)后", text)
    if relative:
        amount = int(relative.group(1))
        if relative.group(2) == "小时":
            amount *= 60
        return now + timedelta(minutes=amount)
    if day is None:
        return None
    clock = _parse_clock(text)
    return datetime.combine(day, clock, tzinfo=default_tz())


def _parse_clock(text: str) -> time:
    value = re.search(r"(\d{1,2})[:：点](\d{1,2})?", text)
    if value:
        hour = int(value.group(1))
        minute = int(value.group(2) or 0)
        if "下午" in text and hour < 12:
            hour += 12
        if "晚上" in text and hour < 12:
            hour += 12
        return time(min(hour, 23), min(minute, 59))
    if "今晚" in text or "晚上" in text:
        return time(20, 0)
    return time(23, 59)


def _parse_duration(text: str) -> int | None:
    value = re.search(r"(\d{1,3})\s*(分钟|小时)", text)
    if not value:
        return None
    amount = int(value.group(1))
    return amount * 60 if value.group(2) == "小时" else amount


_TIME_WORDS = re.compile(
    r"今天|明天|后天|今晚|上午|下午|晚上|中午|下周|周[一二三四五六日天]|"
    r"星期[一二三四五六日天]|之前|以前|截止|点半|\d{1,2}[:：]\d{1,2}|"
    r"\d{1,2}点|\d{1,2}"
)


def _is_time_only(text: str) -> bool:
    """True when nothing is left once the time is stripped ("明天下午三点")."""
    return bool(text) and not _TIME_WORDS.sub("", text).strip()


def _clean_title(text: str) -> str:
    title = re.sub(
        r"(今天|明天|后天|下周|周[一二三四五六日天]|星期[一二三四五六日天])",
        "",
        text,
    )
    title = re.sub(r"^\s*(要|需要|帮我|我要|记得)\s*", "", title)
    title = re.sub(r"\s*(之前|前|截止)\s*$", "", title)
    return title.strip(" ，。；;")[:80]


def _normalize(text: str) -> str:
    return re.sub(r"\W+", "", text).lower()
