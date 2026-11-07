"""Six built-in channels."""

from __future__ import annotations

from channel.builtin.clock import ClockChannel
from channel.builtin.focus import FocusChannel
from channel.builtin.music import MusicChannel
from channel.builtin.plan import PlanChannel
from channel.builtin.reminder import ReminderChannel
from channel.builtin.tasks import TasksChannel
from channel.registry import ChannelRegistry


def default_channels() -> list:
    return [
        ClockChannel(),
        TasksChannel(),
        PlanChannel(),
        FocusChannel(),
        ReminderChannel(),
        MusicChannel(),
    ]


def build_registry() -> ChannelRegistry:
    registry = ChannelRegistry()
    for channel in default_channels():
        registry.register(channel)
    return registry


__all__ = [
    "ClockChannel",
    "FocusChannel",
    "MusicChannel",
    "PlanChannel",
    "ReminderChannel",
    "TasksChannel",
    "build_registry",
    "default_channels",
]
