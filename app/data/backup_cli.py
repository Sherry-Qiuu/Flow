"""CLI for T10/T30 backup."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from data.backup import backup_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up Flow SQLite")
    parser.add_argument(
        "--db", default=os.environ.get("FLOW_DB", "data/flow.db"))
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--keep", type=int, default=7)
    args = parser.parse_args(argv)
    path = Path(args.db)
    try:
        target = backup_database(
            path,
            backup_dir=args.backup_dir,
            keep=args.keep,
        )
    except Exception as exc:
        print(f"backup failed: {exc}")
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
