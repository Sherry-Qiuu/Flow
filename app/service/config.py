"""Configuration loading with YAML defaults and environment overrides."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from planner.timeutil import tz_for
from voice.config import SpeechSettings

_ENV_KEY = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$"
)

# Generic FLOW_* aliases kept for scripts and for T02 compatibility.
_ALIASES = {
    "FLOW_HAL": "hal.backend",
    "FLOW_HOST": "app.host",
    "FLOW_PORT": "app.port",
    "FLOW_TIMEZONE": "app.timezone",
    "FLOW_DB": "data.db_path",
    "FLOW_DATA_DIR": "data.dir",
    "FLOW_BACKUP_DIR": "data.backup_dir",
    "FLOW_BACKUP_KEEP": "data.backup_keep",
    "FLOW_LOG_LEVEL": "logging.level",
    "FLOW_LOG_JSON": "logging.json",
}

_DEFAULTS: dict[str, Any] = {
    "app": {
        "name": "Flow",
        "version": "0.1.0",
        "host": "127.0.0.1",
        "port": 8000,
        "timezone": "Asia/Shanghai",
        "single_worker": True,
    },
    "data": {
        "dir": "data",
        "db_path": "data/flow.db",
        "backup_dir": "data/backup",
        "backup_keep": 7,
        "backup_hour": 3,
    },
    "hal": {
        "backend": "auto",
    },
    "scheduler": {
        "enabled": True,
    },
    "voice": {
        "enabled": True,
        "sample_rate": 16000,
        "pre_roll_s": 3.0,
        "silence_ms": 300,
        "vad_threshold": 0.018,
        "min_speech_ms": 120,
        "partial_interval_ms": 700,
        "max_utterance_s": 30,
        "empty_prompt_after": 3,
        "barge_in": True,
        "barge_in_threshold": 0.03,
        "debug_audio": False,
    },
    "logging": {
        "level": "INFO",
        "json": True,
    },
    "ui": {
        "url": "http://127.0.0.1:8000",
        "size": "720x720",
    },
}


@dataclass(frozen=True)
class AppSettings:
    name: str = "Flow"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    timezone: str = "Asia/Shanghai"
    single_worker: bool = True


@dataclass(frozen=True)
class DataSettings:
    dir: Path = Path("data")
    db_path: Path = Path("data/flow.db")
    backup_dir: Path = Path("data/backup")
    backup_keep: int = 7
    backup_hour: int = 3


@dataclass(frozen=True)
class HalSettings:
    backend: str = "auto"


@dataclass(frozen=True)
class SchedulerSettings:
    enabled: bool = True


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    json: bool = True


@dataclass(frozen=True)
class UiSettings:
    url: str = "http://127.0.0.1:8000"
    size: str = "720x720"


@dataclass(frozen=True)
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    data: DataSettings = field(default_factory=DataSettings)
    hal: HalSettings = field(default_factory=HalSettings)
    scheduler: SchedulerSettings = field(
        default_factory=SchedulerSettings
    )
    voice: SpeechSettings = field(default_factory=SpeechSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    ui: UiSettings = field(default_factory=UiSettings)
    config_path: Path | None = None
    env_file: Path | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Return safe config for logs and /healthz; never includes secrets."""
        return {
            "app": {
                "name": self.app.name,
                "version": self.app.version,
                "host": self.app.host,
                "port": self.app.port,
                "timezone": self.app.timezone,
                "single_worker": self.app.single_worker,
            },
            "data": {
                "dir": str(self.data.dir),
                "db_path": str(self.data.db_path),
                "backup_dir": str(self.data.backup_dir),
                "backup_keep": self.data.backup_keep,
                "backup_hour": self.data.backup_hour,
            },
            "hal": {"backend": self.hal.backend},
            "scheduler": {"enabled": self.scheduler.enabled},
            "voice": {
                "enabled": self.voice.enabled,
                "sample_rate": self.voice.sample_rate,
                "silence_ms": self.voice.silence_ms,
                "max_utterance_s": self.voice.max_utterance_s,
            },
            "logging": {
                "level": self.logging.level,
                "json": self.logging.json,
            },
            "ui": {"url": self.ui.url, "size": self.ui.size},
        }


def default_config_path(env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    configured = values.get("FLOW_CONFIG")
    if configured:
        return Path(configured)
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config
    project_config = Path(__file__).resolve().parents[2] / "config.yaml"
    return project_config


def load_settings(
    path: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
    env_file: str | Path | None = None,
) -> Settings:
    """Load ``config.yaml`` then apply ``FLOW_*`` environment overrides."""
    values = dict(os.environ) if env is None else dict(env)
    config_path = Path(
        path) if path is not None else default_config_path(values)
    base_dir = (
        config_path.parent.resolve()
        if config_path.exists()
        else Path.cwd().resolve()
    )
    raw = _deep_merge(
        _DEFAULTS,
        _read_yaml(config_path),
    )

    selected_env_file = _select_env_file(
        env_file,
        values,
        base_dir,
    )
    dot_values = _read_dotenv(selected_env_file)
    for key, value in dot_values.items():
        values.setdefault(key, value)
        os.environ.setdefault(key, value)

    _apply_aliases(raw, values)
    _apply_nested_overrides(raw, values)
    if (
        "FLOW_DATA_DIR" in values
        and "FLOW_DB" not in values
        and "FLOW_DATA__DB_PATH" not in values
    ):
        raw["data"]["db_path"] = str(
            Path(str(raw["data"]["dir"])) / "flow.db"
        )
    if (
        "FLOW_DATA_DIR" in values
        and "FLOW_BACKUP_DIR" not in values
        and "FLOW_DATA__BACKUP_DIR" not in values
    ):
        raw["data"]["backup_dir"] = str(
            Path(str(raw["data"]["dir"])) / "backup"
        )

    app = AppSettings(
        name=str(raw["app"]["name"]),
        version=str(raw["app"]["version"]),
        host=str(raw["app"]["host"]),
        port=int(raw["app"]["port"]),
        timezone=str(raw["app"]["timezone"]),
        single_worker=bool(raw["app"]["single_worker"]),
    )
    data = DataSettings(
        dir=_resolve_path(base_dir, raw["data"]["dir"]),
        db_path=_resolve_path(base_dir, raw["data"]["db_path"]),
        backup_dir=_resolve_path(base_dir, raw["data"]["backup_dir"]),
        backup_keep=int(raw["data"]["backup_keep"]),
        backup_hour=int(raw["data"]["backup_hour"]),
    )
    hal = HalSettings(backend=str(raw["hal"]["backend"]).lower())
    scheduler = SchedulerSettings(
        enabled=bool(raw["scheduler"]["enabled"])
    )
    voice = SpeechSettings(
        enabled=bool(raw["voice"]["enabled"]),
        sample_rate=int(raw["voice"]["sample_rate"]),
        pre_roll_s=float(raw["voice"]["pre_roll_s"]),
        silence_ms=int(raw["voice"]["silence_ms"]),
        vad_threshold=float(raw["voice"]["vad_threshold"]),
        min_speech_ms=int(raw["voice"]["min_speech_ms"]),
        partial_interval_ms=int(raw["voice"]["partial_interval_ms"]),
        max_utterance_s=int(raw["voice"]["max_utterance_s"]),
        empty_prompt_after=int(raw["voice"]["empty_prompt_after"]),
        barge_in=bool(raw["voice"]["barge_in"]),
        barge_in_threshold=float(raw["voice"]["barge_in_threshold"]),
        debug_audio=bool(raw["voice"]["debug_audio"]),
    )
    logging_settings = LoggingSettings(
        level=str(raw["logging"]["level"]).upper(),
        json=bool(raw["logging"]["json"]),
    )
    ui = UiSettings(
        url=str(raw["ui"]["url"]),
        size=str(raw["ui"]["size"]),
    )
    _validate(app, hal)
    return Settings(
        app=app,
        data=data,
        hal=hal,
        scheduler=scheduler,
        voice=voice,
        logging=logging_settings,
        ui=ui,
        config_path=config_path,
        env_file=selected_env_file,
    )


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read a secret from the process environment; never log the value."""
    return os.environ.get(name, default)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return data


def _select_env_file(
    explicit: str | Path | None,
    values: dict[str, str],
    base_dir: Path,
) -> Path:
    if explicit is not None:
        return Path(explicit)
    configured = values.get("FLOW_ENV_FILE")
    if configured:
        return Path(configured)
    return base_dir / ".env"


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_KEY.match(raw_line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if value[:1] in {'"', "'"}:
            value = value[1:-1] if len(value) >= 2 else value[1:]
        else:
            value = value.split("#", 1)[0].strip()
        result[key] = value
    return result


def _apply_aliases(raw: dict[str, Any], values: dict[str, str]) -> None:
    for env_name, dotted in _ALIASES.items():
        if env_name not in values:
            continue
        _set_dotted(raw, dotted, values[env_name])


def _apply_nested_overrides(
    raw: dict[str, Any],
    values: dict[str, str],
) -> None:
    for key, value in values.items():
        if not key.startswith("FLOW_") or "__" not in key:
            continue
        dotted = key[5:].lower().replace("__", ".")
        if _get_dotted(raw, dotted) is None:
            continue
        _set_dotted(raw, dotted, value)


def _set_dotted(raw: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = raw
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    previous = node.get(parts[-1])
    node[parts[-1]] = _coerce(value, previous)


def _get_dotted(raw: dict[str, Any], dotted: str) -> Any:
    node: Any = raw
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _coerce(value: Any, previous: Any) -> Any:
    if isinstance(previous, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(previous, int):
        return int(value)
    if isinstance(previous, float):
        return float(value)
    return value


def _resolve_path(base_dir: Path, value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _validate(app: AppSettings, hal: HalSettings) -> None:
    if hal.backend not in {"mock", "real", "auto"}:
        raise ValueError(f"unknown hal.backend: {hal.backend!r}")
    if not 1 <= app.port <= 65535:
        raise ValueError("app.port must be in 1..65535")
    try:
        tz_for(app.timezone)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    result = {key: _clone(value) for key, value in base.items()}
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _clone(value)
    return result


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
