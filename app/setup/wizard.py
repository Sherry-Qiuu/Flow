"""T30 first-run configuration and reproducible setup helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def write_first_run_config(
    path: str | Path,
    *,
    name: str,
    nickname: str = "",
    voice: str = "zh",
    chronotype: str = "neutral",
    quiet_start: int = 22,
    quiet_end: int = 7,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    current: dict[str, Any] = {}
    if target.is_file():
        try:
            current = yaml.safe_load(target.read_text("utf-8")) or {}
        except Exception:
            current = {}
    current.setdefault("app", {})["name"] = name or "Flow"
    current.setdefault("voice", {})["voice"] = voice or "zh"
    current.setdefault("voice", {})["quiet_start"] = int(quiet_start)
    current.setdefault("voice", {})["quiet_end"] = int(quiet_end)
    current.setdefault("user", {}).update(
        {
            "name": name,
            "nickname": nickname,
            "chronotype": chronotype,
        }
    )
    target.write_text(
        yaml.safe_dump(current, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def first_run_needed(config_path: str | Path) -> bool:
    target = Path(config_path)
    if not target.is_file():
        return True
    try:
        data = yaml.safe_load(target.read_text("utf-8")) or {}
    except Exception:
        return True
    return not bool(data.get("user", {}).get("name"))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Flow first-run setup")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--name", required=True)
    parser.add_argument("--nickname", default="")
    parser.add_argument("--voice", default="zh")
    parser.add_argument("--chronotype", default="neutral")
    args = parser.parse_args()
    path = write_first_run_config(
        args.config,
        name=args.name,
        nickname=args.nickname,
        voice=args.voice,
        chronotype=args.chronotype,
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
