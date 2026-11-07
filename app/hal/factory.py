"""Backend selection and the aggregate HAL object."""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bus.local import LocalEventBus
from hal.contracts import (
    AudioIn,
    AudioOut,
    Camera,
    Device,
    DeviceStatus,
    Display,
    EventPublisher,
    Gesture,
    PhoneStand,
)
from hal.mock import (
    MockAudioIn,
    MockAudioOut,
    MockCamera,
    MockDisplay,
    MockGesture,
    MockPhoneStand,
)
from hal.real import (
    RealAudioIn,
    RealAudioOut,
    RealCamera,
    RealDisplay,
    RealGesture,
    RealPhoneStand,
)

logger = logging.getLogger(__name__)

BACKENDS = ("mock", "real", "auto")
DEVICE_NAMES = (
    "display",
    "camera",
    "audio_in",
    "audio_out",
    "phone_stand",
    "gesture",
)


@dataclass
class Hal:
    """All devices behind one object.

    ``open_all`` never raises; callers inspect the returned statuses to
    decide whether to show a degraded icon.
    """

    backend: str
    publisher: EventPublisher
    display: Display
    camera: Camera
    audio_in: AudioIn
    audio_out: AudioOut
    phone_stand: PhoneStand
    gesture: Gesture
    fallbacks: dict[str, str] = field(default_factory=dict)

    def devices(self) -> dict[str, Device]:
        return {
            "display": self.display,
            "camera": self.camera,
            "audio_in": self.audio_in,
            "audio_out": self.audio_out,
            "phone_stand": self.phone_stand,
            "gesture": self.gesture,
        }

    def open_all(self) -> dict[str, DeviceStatus]:
        statuses: dict[str, DeviceStatus] = {}
        for name, device in self.devices().items():
            if getattr(device, "is_open", False):
                statuses[name] = device.health()
                continue
            try:
                status = device.open()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("opening %s failed", name)
                status = DeviceStatus.error(str(exc))
            statuses[name] = status
        return statuses

    def probe_all(self) -> dict[str, DeviceStatus]:
        statuses: dict[str, DeviceStatus] = {}
        for name, device in self.devices().items():
            try:
                statuses[name] = device.probe()
            except Exception as exc:  # pragma: no cover - defensive
                statuses[name] = DeviceStatus.error(str(exc))
        return statuses

    def health(self) -> dict[str, DeviceStatus]:
        statuses: dict[str, DeviceStatus] = {}
        for name, device in self.devices().items():
            try:
                statuses[name] = device.health()
            except Exception as exc:  # pragma: no cover - defensive
                statuses[name] = DeviceStatus.error(str(exc))
        return statuses

    def faulted_devices(self) -> dict[str, DeviceStatus]:
        return {
            name: status
            for name, status in self.health().items()
            if not status.available
        }

    def close(self) -> None:
        for name, device in self.devices().items():
            try:
                device.close()
            except Exception:  # pragma: no cover - defensive
                logger.exception("closing %s failed", name)


def _default_backend(env: dict[str, str]) -> str:
    configured = env.get("FLOW_HAL")
    if configured:
        return configured.strip().lower()
    if platform.system() == "Linux":
        model = Path("/proc/device-tree/model")
        try:
            if model.exists() and "raspberry pi" in model.read_text().lower():
                return "auto"
        except OSError:
            pass
    return "mock"


def _mock_device(name: str, publisher: EventPublisher) -> Device:
    factories: dict[str, Any] = {
        "display": lambda: MockDisplay(publisher),
        "camera": lambda: MockCamera(publisher),
        "audio_in": lambda: MockAudioIn(publisher),
        "audio_out": lambda: MockAudioOut(publisher),
        "phone_stand": lambda: MockPhoneStand(publisher),
        "gesture": lambda: MockGesture(publisher),
    }
    return factories[name]()


def _real_device(name: str, publisher: EventPublisher) -> Device:
    factories: dict[str, Any] = {
        "display": RealDisplay,
        "camera": RealCamera,
        "audio_in": RealAudioIn,
        "audio_out": RealAudioOut,
        "phone_stand": lambda: RealPhoneStand(publisher),
        "gesture": RealGesture,
    }
    return factories[name]()


def _build_mock(publisher: EventPublisher) -> dict[str, Device]:
    return {name: _mock_device(name, publisher) for name in DEVICE_NAMES}


def _build_real(publisher: EventPublisher) -> dict[str, Device]:
    return {name: _real_device(name, publisher) for name in DEVICE_NAMES}


def _can_open(device: Device) -> DeviceStatus:
    """Open and immediately release a device to validate auto mode."""
    try:
        status = device.open()
    except Exception as exc:
        return DeviceStatus.error(str(exc))
    try:
        device.close()
    except Exception:  # pragma: no cover - hardware boundary
        logger.exception("closing probe instance failed")
    return status


def create_hal(
    backend: str | None = None,
    publisher: EventPublisher | None = None,
    *,
    env: dict[str, str] | None = None,
) -> Hal:
    """Create the HAL for ``FLOW_HAL`` (or an explicit backend).

    ``mock`` forces fake devices, ``real`` keeps real devices even when
    missing, and ``auto`` falls back per device to a mock.
    """
    environment = dict(os.environ) if env is None else env
    requested = (backend or _default_backend(environment)).strip().lower()
    if requested not in BACKENDS:
        logger.warning("unknown FLOW_HAL=%r, using mock", requested)
        requested = "mock"
    bus: EventPublisher = publisher or LocalEventBus()

    if requested == "mock":
        devices = _build_mock(bus)
        return Hal(requested, bus, **devices)
    if requested == "real":
        devices = _build_real(bus)
        return Hal(requested, bus, **devices)

    devices: dict[str, Device] = {}
    fallbacks: dict[str, str] = {}
    for name in DEVICE_NAMES:
        real = _real_device(name, bus)
        status = _can_open(real)
        if status.available:
            devices[name] = real
        else:
            logger.info(
                "auto mode: %s falls back to mock (%s)",
                name,
                status.detail,
            )
            fallbacks[name] = status.detail or status.state.value
            devices[name] = _mock_device(name, bus)
    return Hal("auto", bus, fallbacks=fallbacks, **devices)
