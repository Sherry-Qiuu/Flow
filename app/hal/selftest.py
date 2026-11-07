"""Boot self-test for every HAL device.

Run it with::

    FLOW_HAL=mock python -m hal.selftest

The service must keep running when a check fails; the report is also
written to the ``device_status`` table so the UI can show a fault icon.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from array import array
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from hal.contracts import DeviceStatus
from hal.factory import Hal, create_hal
from hal.status_store import (
    DeviceStatusRow,
    default_db_path,
    write_device_status,
)

OK = "OK"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass(frozen=True)
class SelfTestCheck:
    device: str
    action: str
    status: str
    detail: str
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "action": self.action,
            "status": self.status,
            "detail": self.detail,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class SelfTestReport:
    backend: str
    checks: list[SelfTestCheck] = field(default_factory=list)
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: datetime | None = None
    db_path: str | None = None
    db_error: str | None = None

    @property
    def ok(self) -> bool:
        return not any(check.status == FAIL for check in self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for check in self.checks if check.status == OK)

    @property
    def failed(self) -> int:
        return sum(1 for check in self.checks if check.status == FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for check in self.checks if check.status == SKIP)

    @property
    def degraded(self) -> bool:
        return any(check.status != OK for check in self.checks)

    def device_rows(self) -> list[DeviceStatusRow]:
        checked_at = self.finished_at or datetime.now(timezone.utc)
        rows: list[DeviceStatusRow] = []
        devices = []
        for check in self.checks:
            if check.device not in devices:
                devices.append(check.device)
        for device in devices:
            checks = [c for c in self.checks if c.device == device]
            if any(c.status == FAIL for c in checks):
                status = "error"
            elif any(c.status == SKIP for c in checks):
                status = "missing"
            else:
                status = "ok"
            detail = "; ".join(
                f"{c.action}: {c.detail}" for c in checks if c.detail
            )
            rows.append(DeviceStatusRow(device, status, detail, checked_at))
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "ok": self.ok,
            "degraded": self.degraded,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "db_path": self.db_path,
            "db_error": self.db_error,
            "checks": [check.to_dict() for check in self.checks],
        }


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _tone_pcm(seconds: float = 0.2, rate: int = 16000) -> bytes:
    samples = array("h")
    total = max(1, int(rate * seconds))
    for index in range(total):
        envelope = min(1.0, index / (rate * 0.01))
        value = math.sin(2.0 * math.pi * 440.0 * index / rate)
        samples.append(int(32767 * 0.2 * envelope * value))
    return samples.tobytes()


def _ready(
    name: str,
    statuses: dict[str, DeviceStatus],
    add: Callable[..., None],
) -> bool:
    status = statuses.get(name)
    if status is None:
        add(name, "open", FAIL, "device was not opened", 0.0)
        return False
    if not status.available:
        add(name, "open", FAIL, status.detail or status.state.value, 0.0)
        return False
    return True


def run_selftest(
    hal: Hal,
    *,
    db_path: str | Path | None = None,
    record: bool = True,
    audio_seconds: float = 1.0,
) -> SelfTestReport:
    """Exercise every device and optionally persist the result."""
    report = SelfTestReport(backend=hal.backend)
    statuses = hal.open_all()

    def add(
        device: str,
        action: str,
        status: str,
        detail: str,
        duration_ms: float,
    ) -> None:
        report.checks.append(
            SelfTestCheck(device, action, status, detail, duration_ms)
        )

    # Display: text, face and backlight are all part of "screen lights up".
    if _ready("display", statuses, add):
        start = time.perf_counter()
        try:
            hal.display.show_text("Flow self-test")
            hal.display.show_face("happy")
            hal.display.set_brightness(0.9)
            add(
                "display",
                "render",
                OK,
                "text, expression and backlight",
                _elapsed_ms(start),
            )
        except Exception as exc:
            add("display", "render", FAIL, str(exc), _elapsed_ms(start))

    # Camera: capture one valid JPEG.
    if _ready("camera", statuses, add):
        start = time.perf_counter()
        try:
            data = hal.camera.capture()
            if not data:
                add("camera", "capture", FAIL, "capture returned no data", 0.0)
            elif not (
                data.startswith(b"\xff\xd8")
                and data.endswith(b"\xff\xd9")
            ):
                add("camera", "capture", FAIL, "not a JPEG frame", 0.0)
            else:
                detail = f"JPEG {len(data) / 1024:.1f} KB"
                add("camera", "capture", OK, detail, _elapsed_ms(start))
        except Exception as exc:
            add("camera", "capture", FAIL, str(exc), _elapsed_ms(start))

    # Microphone: record for the requested duration and inspect frames.
    if _ready("audio_in", statuses, add):
        start = time.perf_counter()
        frames = []
        try:
            status = hal.audio_in.start(frames.append)
            if not status.available:
                add("audio_in", "record", FAIL, status.detail, 0.0)
            else:
                duration = max(0.05, float(audio_seconds))
                time.sleep(duration)
                if not frames:
                    add(
                        "audio_in",
                        "record",
                        FAIL,
                        "no audio frames received",
                        _elapsed_ms(start),
                    )
                elif any(
                    frame.sample_rate != 16000
                    or frame.channels != 1
                    or not frame.pcm
                    for frame in frames
                ):
                    add(
                        "audio_in",
                        "record",
                        FAIL,
                        "frames are not 16 kHz mono PCM",
                        _elapsed_ms(start),
                    )
                else:
                    frame = frames[-1]
                    detail = (
                        f"{len(frames)} frames, "
                        f"{frame.duration_ms:.0f} ms each, "
                        "16000 Hz mono"
                    )
                    add(
                        "audio_in",
                        "record",
                        OK,
                        detail,
                        _elapsed_ms(start),
                    )
        except Exception as exc:
            add("audio_in", "record", FAIL, str(exc), _elapsed_ms(start))
        finally:
            try:
                hal.audio_in.stop()
            except Exception:
                pass

    # Speaker: play a short prompt tone.
    if _ready("audio_out", statuses, add):
        start = time.perf_counter()
        try:
            hal.audio_out.set_volume(0.8)
            if hal.audio_out.play(_tone_pcm()):
                add(
                    "audio_out",
                    "play",
                    OK,
                    "prompt tone (200 ms)",
                    _elapsed_ms(start),
                )
            else:
                add("audio_out", "play", FAIL, "playback failed", 0.0)
        except Exception as exc:
            add("audio_out", "play", FAIL, str(exc), _elapsed_ms(start))

    # Phone stand: a safe snapshot proves the sensor path is readable.
    if _ready("phone_stand", statuses, add):
        start = time.perf_counter()
        try:
            state = hal.phone_stand.state()
            add(
                "phone_stand",
                "read",
                OK,
                (
                    f"present={state.present}, charging={state.charging}, "
                    f"current={state.current_ma} mA, "
                    f"distance={state.distance_mm} mm"
                ),
                _elapsed_ms(start),
            )
        except Exception as exc:
            add("phone_stand", "read", FAIL, str(exc), _elapsed_ms(start))

    report.finished_at = datetime.now(timezone.utc)
    if record:
        path = Path(db_path) if db_path is not None else default_db_path()
        try:
            write_device_status(report.device_rows(), path)
            report.db_path = str(path)
        except Exception as exc:  # pragma: no cover - disk boundary
            report.db_error = str(exc)
    return report


def format_report(report: SelfTestReport) -> str:
    lines = [f"Flow HAL self-test (backend={report.backend})"]
    for check in report.checks:
        lines.append(
            f"[{check.status:<4}] {check.device:<11} "
            f"{check.action:<8} {check.duration_ms:7.1f} ms  {check.detail}"
        )
    lines.append(
        f"SELF-TEST: {report.passed} OK, {report.failed} FAIL, "
        f"{report.skipped} SKIP"
    )
    if report.db_path:
        lines.append(f"device_status -> {report.db_path}")
    if report.db_error:
        lines.append(f"device_status write failed: {report.db_error}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flow HAL boot self-test")
    parser.add_argument(
        "--backend",
        choices=("mock", "real", "auto"),
        default=None,
        help="override FLOW_HAL",
    )
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="do not write device_status",
    )
    parser.add_argument(
        "--audio-seconds",
        type=float,
        default=1.0,
        help="microphone recording duration (default: 1.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the report as JSON",
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
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
