"""Flow hardware abstraction layer.

Quick start::

    FLOW_HAL=mock python -m hal.selftest

The package exposes one contract per device plus mock and real
implementations. Upper layers should use the contract types only.
"""

from hal.contracts import (
    AudioFrame,
    AudioIn,
    AudioOut,
    Camera,
    Device,
    DeviceState,
    DeviceStatus,
    Display,
    EventPublisher,
    Gesture,
    NullPublisher,
    PhoneStand,
    PhoneState,
)
from hal.factory import Hal, create_hal
from hal.runtime import close_hal, get_hal, reset_hal

__all__ = [
    "AudioFrame",
    "AudioIn",
    "AudioOut",
    "Camera",
    "Device",
    "DeviceState",
    "DeviceStatus",
    "Display",
    "EventPublisher",
    "Gesture",
    "Hal",
    "NullPublisher",
    "PhoneStand",
    "PhoneState",
    "close_hal",
    "create_hal",
    "get_hal",
    "reset_hal",
]
