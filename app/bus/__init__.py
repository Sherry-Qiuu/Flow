"""Event bus primitives shared by the Flow backend.

T03 owns the production event bus. This package currently provides the
small, thread-safe adapter the HAL needs to publish ``phone.changed``
without depending on the full FastAPI service.
"""

from bus.local import LocalEventBus

__all__ = ["LocalEventBus"]
