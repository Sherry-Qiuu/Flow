"""Event bus primitives shared by the Flow backend.

T03 owns the production event bus. ``EventBus`` is the asyncio service
bus; ``LocalEventBus`` remains a tiny synchronous adapter for standalone
HAL tests.
"""

from bus.event_bus import EventBus, EventMessage
from bus.local import LocalEventBus

__all__ = ["EventBus", "EventMessage", "LocalEventBus"]
