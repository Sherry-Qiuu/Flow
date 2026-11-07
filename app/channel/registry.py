"""T04 channel registry."""

from __future__ import annotations

from channel.base import Channel


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    def register(self, channel: Channel) -> None:
        if not channel.key or not channel.title:
            raise ValueError("channel key and title are required")
        if channel.key in self._channels:
            raise ValueError(f"duplicate channel: {channel.key}")
        self._channels[channel.key] = channel

    def get(self, key: str) -> Channel:
        try:
            return self._channels[key]
        except KeyError as exc:
            raise KeyError(f"unknown channel: {key}") from exc

    def has(self, key: str) -> bool:
        return key in self._channels

    def keys(self) -> list[str]:
        return list(self._channels)

    def list(self) -> list[dict[str, str]]:
        return [
            {"key": channel.key, "title": channel.title}
            for channel in self._channels.values()
        ]
