"""Process-wide HAL accessor used by the backend service."""

from __future__ import annotations

import threading

from hal.contracts import EventPublisher
from hal.factory import Hal, create_hal

_lock = threading.RLock()
_hal: Hal | None = None


def get_hal(
    backend: str | None = None,
    publisher: EventPublisher | None = None,
    *,
    force: bool = False,
) -> Hal:
    """Return the shared HAL, creating it on first use."""
    global _hal
    with _lock:
        if _hal is None or force:
            if _hal is not None:
                _hal.close()
            _hal = create_hal(backend, publisher)
        return _hal


def close_hal() -> None:
    """Close the shared HAL, if any."""
    global _hal
    with _lock:
        if _hal is not None:
            _hal.close()
            _hal = None


def reset_hal() -> None:
    """Test helper: drop the cached HAL without touching other modules."""
    close_hal()
