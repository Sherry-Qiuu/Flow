"""Small status value object shared by backend subsystems."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    state: str
    detail: str = ""
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False,
    )

    @property
    def healthy(self) -> bool:
        return self.state in {"ok", "disabled"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }

    @classmethod
    def ok(cls, name: str, detail: str = "") -> "ServiceStatus":
        return cls(name, "ok", detail)

    @classmethod
    def disabled(cls, name: str, detail: str = "") -> "ServiceStatus":
        return cls(name, "disabled", detail)

    @classmethod
    def degraded(cls, name: str, detail: str = "") -> "ServiceStatus":
        return cls(name, "degraded", detail)

    @classmethod
    def error(cls, name: str, detail: str = "") -> "ServiceStatus":
        return cls(name, "error", detail)
