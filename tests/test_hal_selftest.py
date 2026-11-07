"""Boot self-test and device_status persistence tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hal.daemon import main as daemon_main
from hal.factory import create_hal
from hal.selftest import FAIL, OK, run_selftest
from hal.status_store import read_device_status


def test_selftest_reports_every_device_and_writes_db(workspace_tmp):
    hal = create_hal("mock")
    db_path = workspace_tmp / "selftest.db"
    db_path.unlink(missing_ok=True)
    try:
        report = run_selftest(hal, db_path=db_path, audio_seconds=0.15)
    finally:
        hal.close()
    assert report.ok
    assert report.failed == 0
    assert len(report.checks) == 5
    assert all(check.status == OK for check in report.checks)
    assert report.db_path == str(db_path)
    rows = read_device_status(db_path)
    assert len(rows) == 5
    assert {row["device"] for row in rows} == {
        "display",
        "camera",
        "audio_in",
        "audio_out",
        "phone_stand",
    }
    assert all(row["status"] == "ok" for row in rows)


def test_selftest_keeps_running_when_camera_is_missing():
    hal = create_hal("mock")
    hal.camera.unplug()
    try:
        report = run_selftest(hal, record=False, audio_seconds=0.1)
    finally:
        hal.close()
    assert not report.ok
    checks = {check.device: check for check in report.checks}
    assert checks["camera"].status == FAIL
    assert checks["display"].status == OK
    assert checks["audio_in"].status == OK
    assert checks["phone_stand"].status == OK


def test_selftest_cli_command(workspace_tmp):
    root = Path(__file__).resolve().parents[1]
    db_path = workspace_tmp / "cli.db"
    db_path.unlink(missing_ok=True)
    env = dict(os.environ)
    env["FLOW_HAL"] = "mock"
    env["PYTHONPATH"] = str(root / "app")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hal.selftest",
            "--audio-seconds",
            "0.1",
            "--db",
            str(db_path),
        ],
        cwd=root / "app",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "SELF-TEST: 5 OK, 0 FAIL, 0 SKIP" in result.stdout
    assert "[OK" in result.stdout
    assert db_path.exists()


def test_hal_daemon_preflight_is_non_strict(capsys):
    code = daemon_main(
        [
            "--backend",
            "mock",
            "--no-db",
            "--audio-seconds",
            "0.1",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "mock"
    assert payload["ok"] is True
    assert len(payload["checks"]) == 5
