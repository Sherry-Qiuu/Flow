"""Boot preflight for T01's ``flow-hal.service``.

The backend owns the HAL in-process for T03, so this command runs the
T02 self-test, writes ``device_status`` and exits. Running it before
``flow-backend`` avoids two processes opening the camera and microphone
at the same time. Use ``--strict`` in CI when a non-ok result must fail
the unit.
"""

from __future__ import annotations

import argparse
import sys

from hal.factory import create_hal
from hal.selftest import format_report, run_selftest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flow HAL boot preflight / self-test",
    )
    parser.add_argument(
        "--backend",
        choices=("mock", "real", "auto"),
        default=None,
    )
    parser.add_argument("--db", default=None)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--audio-seconds", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when a required device fails",
    )
    args = parser.parse_args(argv)

    hal = create_hal(args.backend)
    try:
        report = run_selftest(
            hal,
            db_path=args.db,
            record=not args.no_db,
            audio_seconds=args.audio_seconds,
        )
    finally:
        hal.close()

    if args.json:
        import json

        print(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_report(report))
    if args.strict and not report.ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
