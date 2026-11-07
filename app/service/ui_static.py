"""Resolve the built T05 UI without depending on the current directory."""

from __future__ import annotations

from pathlib import Path


def find_ui_dist() -> Path | None:
    candidates = [
        Path.cwd() / "ui" / "dist",
        Path(__file__).resolve().parents[2] / "ui" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None
