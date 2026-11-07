"""Test fixtures.

The default pytest temp root is occasionally locked down by the DSH
Windows file sandbox. A workspace-local temporary directory keeps the
suite runnable in that environment and behaves the same on CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"


@pytest.fixture
def workspace_tmp() -> Path:
    """A writable workspace directory shared by tests.

    Creating new directories from inside the DSH Windows sandbox can
    produce a restrictive ACL, so tests write files directly here and
    use unique names.
    """
    _TEST_ROOT.mkdir(exist_ok=True)
    yield _TEST_ROOT
