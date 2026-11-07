"""T01 deployment asset and hardware-runbook checks."""

from __future__ import annotations

import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_install_script_and_units_exist():
    for relative in (
        "install.sh",
        "deploy/flow-kiosk.sh",
        "deploy/configure-display.sh",
        "deploy/flow-diag",
        "deploy/xbindkeysrc",
        "deploy/systemd/flow-hal.service",
        "deploy/systemd/flow-backend.service",
        "deploy/systemd/flow-ui.service",
        "deploy/systemd/journald-flow.conf",
    ):
        assert (ROOT / relative).is_file(), relative


def test_systemd_units_have_ordered_services():
    hal = configparser.ConfigParser(strict=False)
    hal.read(ROOT / "deploy/systemd/flow-hal.service", encoding="utf-8")
    assert hal["Service"]["Type"].lower() == "oneshot"
    assert "hal.daemon" in hal["Service"]["ExecStart"]

    backend = configparser.ConfigParser(strict=False)
    backend.read(
        ROOT / "deploy/systemd/flow-backend.service",
        encoding="utf-8",
    )
    assert backend["Service"]["Restart"].lower() == "always"
    assert "app.main:app" in backend["Service"]["ExecStart"]
    assert "workers 1" in backend["Service"]["ExecStart"]
    assert "flow-hal.service" in backend["Unit"]["After"]

    ui = configparser.ConfigParser(strict=False)
    ui.read(ROOT / "deploy/systemd/flow-ui.service", encoding="utf-8")
    assert ui["Service"]["Restart"].lower() == "always"
    assert "flow-backend.service" in ui["Unit"]["After"]
    assert "xinit" in ui["Service"]["ExecStart"]


def test_install_script_bootstraps_venv_units_and_diag():
    script = read("install.sh")
    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    assert "python3 -m venv --system-site-packages" in script
    assert "flow-hal.service flow-backend.service flow-ui.service" in script
    assert "flow-diag" in script
    assert "systemctl set-default multi-user.target" in script


def test_display_and_kiosk_assets():
    display = read("deploy/configure-display.sh")
    assert "hdmi_cvt=720 720 60 6" in display
    assert "flow display managed" in display
    kiosk = read("deploy/flow-kiosk.sh")
    assert "--kiosk" in kiosk
    assert "--window-size=720,720" in kiosk
    assert "xbindkeys" in kiosk
    assert "Control+w" in read("deploy/xbindkeysrc")


def test_diag_collects_journal_config_and_sensor_status():
    diag = read("deploy/flow-diag")
    assert "journalctl" in diag
    assert "config.yaml" in diag
    assert "device_status" in diag
    assert "hal.selftest" in diag
    assert ".env" not in diag


def test_env_example_has_empty_secret_values():
    values: dict[str, str] = {}
    for line in read(".env.example").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    assert values["DEEPSEEK_API_KEY"] == ""
    assert values["QWEN_API_KEY"] == ""
    assert values["DASHSCOPE_API_KEY"] == ""


def test_gitignore_ignores_env_but_keeps_example():
    ignore = read(".gitignore")
    assert "\n.env" in ignore
    assert "!.env.example" in ignore


def test_hardware_runbook_exists_with_commands():
    path = ROOT / "docs/deployment/T01-hardware-runbook.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "install.sh" in text
    assert "flow-hal" in text
    assert "curl" in text
    assert "90 秒" in text


def test_hardware_handoff_doc_covers_team_handoff():
    path = ROOT / "docs/deployment/T01-hardware-handoff.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for token in (
        "交接边界",
        "物料清单",
        "GPIO27",
        "flow-hal",
        "flow-backend",
        "flow-ui",
        "T01-01",
        "T02-07",
        "签收",
        "T20-HW",
    ):
        assert token in text, token
    assert "T01-hardware-runbook.md" in text
    assert "T01" in text and "T02" in text
