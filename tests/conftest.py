"""Test fixtures.

The default pytest temp root is occasionally locked down by the DSH
Windows file sandbox. A workspace-local temporary directory keeps the
suite runnable in that environment and behaves the same on CI.

Each run gets its own subdirectory and removes it afterwards. The first
version of this fixture handed every test the same shared directory and
never cleaned up, so repeated local runs left 240 MB of orphaned SQLite
files and 2000 stray paths behind.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path

import pytest

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
# On Windows the runtime's SQLite handles are still open when the session
# finalizer runs, so the run directory often survives its own cleanup and goes
# away a moment later. Sweeping older runs at the next start keeps the residue
# at one run instead of letting it grow forever.
_STALE_AFTER_S = 5 * 60


def _remove(path: Path) -> None:
    """Delete a directory, retrying once: Windows can still hold a WAL file."""
    for _ in range(2):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.2)


@pytest.fixture(scope="session")
def run_root() -> Path:
    """One directory per test run, removed when the session ends."""
    _TEST_ROOT.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in _TEST_ROOT.glob("run-*"):
        try:
            if old.is_dir() and now - old.stat().st_mtime > _STALE_AFTER_S:
                _remove(old)
        except OSError:
            continue
    root = _TEST_ROOT / f"run-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        _remove(root)


@pytest.fixture
def workspace_tmp(run_root: Path) -> Path:
    """A writable workspace directory shared by the tests in one run.

    Creating new directories from inside the DSH Windows sandbox can
    produce a restrictive ACL, so tests write files directly here and
    use unique names.
    """
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root
