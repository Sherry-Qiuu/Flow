"""T29 capability degradation matrix and user-facing errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    name: str
    available: bool
    fallback: str


class DegradeMatrix:
    def __init__(self, hal: Any = None) -> None:
        self.hal = hal

    def capabilities(self) -> list[Capability]:
        devices = {}
        if self.hal is not None:
            if hasattr(self.hal, "device_snapshot"):
                devices = self.hal.device_snapshot()
            elif hasattr(self.hal, "health"):
                devices = {
                    name: {"available": status.available}
                    for name, status in self.hal.health().items()
                }

        def ok(name: str, default: bool = False) -> bool:
            item = devices.get(name, {})
            if isinstance(item, dict):
                if "available" in item:
                    return bool(item.get("available", default))
                if "state" in item:
                    return item.get("state") == "ok"
            return default
        return [
            Capability("display", ok("display"),
                       "screen remains the primary output"),
            Capability("camera", ok("camera"), "voice/text capture only"),
            Capability("microphone", ok("audio_in"),
                       "screen + touch + manual buttons"),
            Capability("speaker", ok("audio_out"), "text-only responses"),
            Capability("phone_sensor", ok("phone_stand"),
                       "manual take/return API"),
        ]

    def snapshot(self) -> dict[str, Any]:
        caps = self.capabilities()
        return {
            "items": [cap.__dict__ for cap in caps],
            "missing": [cap.name for cap in caps if not cap.available],
            "ok": all(cap.available for cap in caps),
        }


ERROR_MESSAGES = {
    "asr": "我没听清，再说一次",
    "tts": "我先把这句话写在屏幕上",
    "network": "现在用离线方式继续",
    "camera": "摄像头暂时不可用，可以先用语音或文字",
    "database": "数据暂时没保存上，我们再试一次",
    "unknown": "刚才没成功，我们再来一次",
}


def user_message(kind: str = "unknown") -> str:
    return ERROR_MESSAGES.get(kind, ERROR_MESSAGES["unknown"])
