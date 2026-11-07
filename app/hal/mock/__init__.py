"""Hardware-free HAL implementations.

Set ``FLOW_HAL=mock`` to force every device to use these classes. This
is the default on developer machines and in CI.
"""

from hal.mock.audio import MockAudioIn
from hal.mock.audio_out import MockAudioOut
from hal.mock.camera import MockCamera
from hal.mock.display import MockDisplay
from hal.mock.gesture import MockGesture
from hal.mock.phone_stand import MockPhoneStand

__all__ = [
    "MockAudioIn",
    "MockAudioOut",
    "MockCamera",
    "MockDisplay",
    "MockGesture",
    "MockPhoneStand",
]
