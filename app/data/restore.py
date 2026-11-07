"""Restore a Flow database from a T10 backup.

Usage::

    python -m data.restore --db data/flow.db --latest
    python -m data.restore --db data/flow.db --backup data/backup/flow-....db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from data.backup import latest_backup, list_backups, restore_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore Flow SQLite")
    parser.add_argument(
        "--db",
        default=os.environ.get("FLOW_DB", "data/flow.db"),
        help="target database (default: FLOW_DB or data/flow.db)",
    )
    parser.add_argument("--backup", help="explicit backup file")
    parser.add_argument("--backup-dir", help="directory for --latest")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="use the newest backup in --backup-dir",
    )
    parser.add_argument("--list", action="store_true", help="list backups")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    backup_dir = (
        Path(args.backup_dir)
        if args.backup_dir
        else db_path.parent / "backup"
    )
    if args.list:
        for path in list_backups(backup_dir):
            print(path)
        return 0

    source: Path | None
    if args.backup:
        source = Path(args.backup)
    elif args.latest:
        source = latest_backup(backup_dir)
    else:
        parser.error("use --backup PATH, --latest or --list")
        return 2
    if source is None:
        print(f"no backup found in {backup_dir}", file=sys.stderr)
        return 1

    try:
        target = restore_database(source, db_path)
    except Exception as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1
    print(f"restored {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
