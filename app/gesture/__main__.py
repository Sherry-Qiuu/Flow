"""Standalone gesture daemon / demo.

Run on the device after the HAL is available::

    python -m gesture --backend real
    python -m gesture --backend mock --demo
"""

from __future__ import annotations

import argparse
import json
import time

from bus import topics
from bus.local import LocalEventBus
from gesture.config import GestureSettings
from gesture.service import GestureService
from hal.factory import create_hal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flow gesture service")
    parser.add_argument(
        "--backend",
        choices=("mock", "real", "auto"),
        default="mock",
    )
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="inject a wave and phone placement after start",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bus = LocalEventBus()
    hal = create_hal(args.backend, publisher=bus)
    service: GestureService | None = None

    def on_gesture(payload: dict) -> None:
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"{payload.get('type')} -> {payload.get('action')} "
                f"({payload.get('source')})"
            )

    bus.subscribe(topics.GESTURE_DETECTED, on_gesture)
    try:
        hal.open_all()
        service = GestureService(
            GestureSettings(),
            bus,
            hal.gesture,
            hal.phone_stand,
        )
        health = service.start()
        if not args.json:
            print(
                f"gesture service: {health.state} ({health.detail})"
            )
        if args.demo:
            trigger = getattr(hal.gesture, "trigger", None)
            if callable(trigger):
                trigger("wave")
                time.sleep(0.1)
                trigger("right")
            place = getattr(hal.phone_stand, "place_phone", None)
            if callable(place):
                place()
        time.sleep(max(0.1, args.seconds))
    finally:
        if service is not None:
            service.stop()
        hal.close()
        if args.json:
            print(
                json.dumps(
                    {
                        "service": service.health().to_dict()
                        if service is not None
                        else None,
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
