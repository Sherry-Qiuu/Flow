"""T03 event bus tests."""

from __future__ import annotations

import asyncio
import threading

from bus.event_bus import EventBus


def test_publish_async_awaits_handlers_and_wildcards():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        exact: list[dict] = []
        wildcard: list[dict] = []

        bus.subscribe("phone.changed", exact.append)
        bus.subscribe("phone.*", wildcard.append)
        message = await bus.publish_async(
            "phone.changed",
            {"present": True},
        )
        assert message.seq == 1
        assert message.ts.endswith("Z")
        assert exact == [{"present": True}]
        assert wildcard == [{"present": True}]
        await bus.aclose()

    asyncio.run(scenario())


def test_envelope_subscription_receives_protocol_message():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        received: list[dict] = []
        bus.subscribe("*", received.append, envelope=True)
        await bus.publish_async("phone.changed", {"present": False})
        assert received[0]["type"] == "phone.changed"
        assert received[0]["payload"] == {"present": False}
        assert received[0]["seq"] == 1
        await bus.aclose()

    asyncio.run(scenario())


def test_sequence_increases_monotonically():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        first = await bus.publish_async("a.event", {})
        second = await bus.publish_async("b.event", {})
        assert second.seq == first.seq + 1
        await bus.aclose()

    asyncio.run(scenario())


def test_thread_publish_is_delivered_on_loop():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        received = threading.Event()
        payloads: list[dict] = []

        def handler(payload: dict) -> None:
            payloads.append(payload)
            received.set()

        bus.subscribe("phone.changed", handler)

        def worker() -> None:
            bus.publish("phone.changed", {"present": True})

        await asyncio.to_thread(worker)
        assert await asyncio.to_thread(received.wait, 1.0)
        assert payloads == [{"present": True}]
        await bus.aclose()

    asyncio.run(scenario())


def test_handler_error_does_not_stop_other_handlers():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        received: list[str] = []

        def broken(payload: dict) -> None:
            del payload
            raise RuntimeError("boom")

        bus.subscribe("event", broken)
        bus.subscribe("event", lambda payload: received.append("ok"))
        await bus.publish_async("event", {})
        assert received == ["ok"]
        await bus.aclose()

    asyncio.run(scenario())


def test_aclose_cancels_pending_dispatch():
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        bus.subscribe("event", lambda payload: None)
        bus.publish("event", {})
        await bus.aclose()
        assert bus._closed is True

    asyncio.run(scenario())
