"""T03 configuration tests."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from service.config import DataSettings, get_secret, load_settings


def write_config(root: Path, body: str) -> Path:
    path = root / f"config-{uuid.uuid4().hex}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_are_loaded_when_config_is_missing(workspace_tmp):
    settings = load_settings(
        workspace_tmp / "does-not-exist.yaml",
        env={"FLOW_HAL": "mock"},
        env_file=workspace_tmp / "missing.env",
    )
    assert settings.app.port == 8000
    assert settings.hal.backend == "mock"
    assert settings.data.db_path.name == "flow.db"


def test_yaml_and_env_override(workspace_tmp):
    path = write_config(
        workspace_tmp,
        """
app:
  port: 8100
  timezone: Asia/Shanghai
data:
  dir: state
  db_path: state/flow.db
hal:
  backend: mock
logging:
  level: WARNING
  json: false
""",
    )
    settings = load_settings(
        path,
        env={
            "FLOW_APP__PORT": "8200",
            "FLOW_HAL": "auto",
            "FLOW_DATA_DIR": "runtime-data",
        },
        env_file=workspace_tmp / "missing.env",
    )
    assert settings.app.port == 8200
    assert settings.hal.backend == "auto"
    assert settings.data.dir.name == "runtime-data"
    assert settings.data.db_path.name == "flow.db"
    assert settings.data.db_path.parent == settings.data.dir
    assert settings.logging.level == "WARNING"
    assert settings.logging.json is False


def test_dotenv_is_loaded_without_overriding_real_env(workspace_tmp):
    env_file = workspace_tmp / f"dotenv-{uuid.uuid4().hex}.env"
    secret_name = f"FLOW_TEST_SECRET_{uuid.uuid4().hex.upper()}"
    env_file.write_text(
        f"{secret_name}=sk-test-only\n",
        encoding="utf-8",
    )
    os.environ.pop(secret_name, None)
    try:
        settings = load_settings(
            env={"FLOW_HAL": "mock"},
            env_file=env_file,
        )
        assert settings.hal.backend == "mock"
        assert get_secret(secret_name) == "sk-test-only"
        assert "sk-test-only" not in str(settings.to_public_dict())
    finally:
        os.environ.pop(secret_name, None)


def test_public_config_has_no_secret_fields():
    settings = load_settings(env={"FLOW_HAL": "mock"})
    public = settings.to_public_dict()
    assert "DEEPSEEK_API_KEY" not in str(public)
    assert "api_key" not in str(public).lower()


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"FLOW_HAL": "bad"}, "hal.backend"),
        ({"FLOW_APP__PORT": "70000"}, "port"),
        ({"FLOW_TIMEZONE": "Mars/Olympus"}, "time zone"),
        # A non-numeric override must name the key, not raise a bare
        # ValueError with a traceback.
        ({"FLOW_PORT": "abc"}, "config override app.port: expected an integer"),
        ({"FLOW_VOICE__SILENCE_MS": "soon"}, "expected an integer"),
    ],
)
def test_invalid_configuration_is_rejected(env, message):
    with pytest.raises(ValueError, match=message):
        load_settings(env={"FLOW_HAL": "mock", **env})


def test_data_settings_coerces_string_paths():
    """A plain dataclass does not coerce, so ``dir`` stayed a str.

    ``runtime.start`` then did ``data.dir / 'audio'`` and raised
    ``TypeError: unsupported operand type(s) for /``.
    """
    data = DataSettings(dir="data", db_path="data/flow.db")
    assert isinstance(data.dir, Path)
    assert isinstance(data.db_path, Path)
    assert isinstance(data.backup_dir, Path)
    assert data.dir / "audio" == Path("data/audio")

