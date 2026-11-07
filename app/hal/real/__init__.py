"""Hardware-backed HAL implementations.

Every class degrades to ``DeviceStatus.missing`` or ``error`` instead of
raising when a peripheral is absent. Optional third-party libraries are
imported lazily so a developer machine can import this package safely.
"""

from hal.real.audio import RealAudioIn, RealAudioOut
from hal.real.camera import RealCamera
from hal.real.display import RealDisplay
from hal.real.gesture import RealGesture
from hal.real.phone_stand import RealPhoneStand

__all__ = [
    "RealAudioIn",
    "RealAudioOut",
    "RealCamera",
    "RealDisplay",
    "RealGesture",
    "RealPhoneStand",
]
