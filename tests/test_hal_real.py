"""Real HAL logic that can be tested without the hardware attached."""

from __future__ import annotations

import hal.real.display as display_module
from hal.real.display import RealDisplay
from hal.real.gesture import PAJ7620_CODES, RealGesture, map_code


def test_hdmi_connected_display_is_available_without_backlight(
    workspace_tmp,
    monkeypatch,
):
    status_path = workspace_tmp / "drm-status"
    status_path.write_text("connected\n", encoding="utf-8")

    def fake_glob(pattern: str):
        if pattern.endswith("/status"):
            return [str(status_path)]
        return []

    monkeypatch.setattr(display_module.glob, "glob", fake_glob)
    display = RealDisplay()
    status = display.probe()
    assert status.available
    assert "HDMI" in status.detail


def test_disconnected_display_is_missing(workspace_tmp, monkeypatch):
    status_path = workspace_tmp / "drm-status"
    status_path.write_text("disconnected\n", encoding="utf-8")

    def fake_glob(pattern: str):
        if pattern.endswith("/status"):
            return [str(status_path)]
        return []

    monkeypatch.setattr(display_module.glob, "glob", fake_glob)
    monkeypatch.setattr(
        display_module.Path,
        "exists",
        lambda self: False,
    )
    status = RealDisplay().probe()
    assert not status.available


def test_paj7620_code_mapping():
    assert map_code(0x01) == "up"
    assert map_code(0x100) == "wave"
    assert map_code(0x08) == "right"
    assert map_code(0x999) is None
    assert map_code(None) is None
    assert len(PAJ7620_CODES) == 9


def test_real_gesture_reports_missing_on_this_platform():
    # CI/desktop has no PAJ7620 and no Linux I2C, so it must degrade cleanly.
    status = RealGesture().probe()
    assert status.available is False
    assert status.detail
