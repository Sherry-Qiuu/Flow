"""Music channel; T11/T12 can replace the demo player later."""

from __future__ import annotations

from typing import Any

from channel.base import Action, BaseChannel, ChannelContext, Intent


class MusicChannel(BaseChannel):
    key = "music"
    title = "音乐"

    def __init__(self) -> None:
        super().__init__()
        self._playing = False
        self._track = "轻音乐 · 专注"

    def enter(
        self,
        ctx: ChannelContext,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ctx = ctx
        if args and args.get("track"):
            self._track = str(args["track"])
        return self._finish(
            {"playing": self._playing, "track": self._track},
            ["说“播放”或“暂停”"],
        )

    def exit(self) -> None:
        self._playing = False
        super().exit()

    def handle(self, intent: Intent) -> list[Action]:
        if intent.name in {"play", "music_play"}:
            self._playing = True
        elif intent.name in {"pause", "music_pause"}:
            self._playing = False
        elif intent.name == "next":
            self._track = "白噪音 · 雨"
        elif intent.name == "back":
            return [Action("back", {})]
        self._finish(
            {"playing": self._playing, "track": self._track},
            self.snapshot()["hints"],
        )
        return [Action("music.state", self.snapshot()["data"])]
