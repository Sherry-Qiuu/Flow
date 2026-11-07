"""Hardware abstraction layer contracts.

Upper layers must talk to these interfaces only. A missing or broken
device is reported as a :class:`DeviceStatus` instead of raising, so the
service can keep running in a degraded mode.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


class DeviceState(str, Enum):
    """Health states shared by every device."""

    OK = "ok"
    MISSING = "missing"
    ERROR = "error"


@dataclass(frozen=True)
class DeviceStatus:
    """Result of a probe, open or health check."""

    state: DeviceState
    detail: str = ""
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False,
    )

    @property
    def available(self) -> bool:
        return self.state is DeviceState.OK

    def __bool__(self) -> bool:
        return self.available

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }

    @classmethod
    def ok(cls, detail: str = "") -> "DeviceStatus":
        return cls(DeviceState.OK, detail)

    @classmethod
    def missing(cls, detail: str = "") -> "DeviceStatus":
        return cls(DeviceState.MISSING, detail)

    @classmethod
    def error(cls, detail: str = "") -> "DeviceStatus":
        return cls(DeviceState.ERROR, detail)


@dataclass(frozen=True)
class AudioFrame:
    """One block of mono 16-bit PCM audio."""

    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1
    captured_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False,
    )

    @property
    def samples(self) -> int:
        return len(self.pcm) // (2 * self.channels)

    @property
    def duration_ms(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return self.samples * 1000.0 / self.sample_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "samples": self.samples,
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass(frozen=True)
class PhoneState(Mapping[str, Any]):
    """Snapshot of the phone stand sensors.

    It behaves like the plain dict promised by the task card while still
    offering attribute access to the rest of the backend.
    """

    present: bool = False
    charging: bool = False
    current_ma: int = 0
    distance_mm: int = -1

    def __getitem__(self, key: str) -> Any:
        if key in ("present", "charging", "current_ma", "distance_mm"):
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(
            ("present", "charging", "current_ma", "distance_mm")
        )

    def __len__(self) -> int:
        return 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "charging": self.charging,
            "current_ma": int(self.current_ma),
            "distance_mm": int(self.distance_mm),
        }


@runtime_checkable
class EventPublisher(Protocol):
    """Anything the HAL can publish domain events to."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        ...


class NullPublisher:
    """Publisher used when no event bus was supplied."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        del topic, payload


class Device(ABC):
    """Common lifecycle for every HAL device."""

    name: str = "device"

    def __init__(self) -> None:
        self._opened = False

    @property
    def is_open(self) -> bool:
        return self._opened

    @abstractmethod
    def probe(self) -> DeviceStatus:
        """Check whether the device is present without opening it."""

    @abstractmethod
    def open(self) -> DeviceStatus:
        """Acquire the device. Must not raise for missing hardware."""

    @abstractmethod
    def close(self) -> None:
        """Release the device. Always safe to call repeatedly."""

    def health(self) -> DeviceStatus:
        """Re-check a device that is already in use."""
        return self.probe()


class Display(Device):
    """Screen or backlight control."""

    name = "display"

    @abstractmethod
    def show_face(self, emotion: str) -> None:
        ...

    @abstractmethod
    def show_text(self, text: str) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def set_brightness(self, value: float) -> None:
        """Set brightness in the inclusive 0.0-1.0 range."""


class Camera(Device):
    """Still camera returning JPEG bytes."""

    name = "camera"

    @abstractmethod
    def capture(self) -> bytes | None:
        """Return a JPEG frame, or ``None`` when unavailable."""


class AudioIn(Device):
    """Microphone exposing a callback of 16 kHz mono frames."""

    name = "audio_in"

    @abstractmethod
    def start(self, on_frame: Callable[[AudioFrame], None]) -> DeviceStatus:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...


class AudioOut(Device):
    """Speaker accepting a file path or raw 16-bit PCM bytes."""

    name = "audio_out"

    @abstractmethod
    def play(self, path_or_pcm: str | Path | bytes) -> bool:
        ...

    def stop(self) -> None:
        """Best-effort interrupt for T06 barge-in."""
        return None

    @abstractmethod
    def set_volume(self, value: float) -> None:
        """Set volume in the inclusive 0.0-1.0 range."""

    @property
    @abstractmethod
    def volume(self) -> float:
        ...


class PhoneStand(Device):
    """Phone presence, charging current and distance sensors."""

    name = "phone_stand"

    @abstractmethod
    def state(self) -> PhoneState:
        """Return the latest safe snapshot, even when unavailable."""
