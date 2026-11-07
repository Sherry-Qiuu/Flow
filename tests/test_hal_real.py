"""Real HAL logic that can be tested without the hardware attached."""

from __future__ import annotations

import hal.real.display as display_module
from hal.real.display import RealDisplay


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
