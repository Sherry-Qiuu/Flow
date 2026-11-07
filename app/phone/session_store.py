"""T20 phone presence, debounce and session persistence."""

from __future__ import annotations

from dataclasses import dataclass

from data.repositories import PhoneSessionRepository


@dataclass(frozen=True)
class PhoneSnapshot:
    present: bool = False
    charging: bool = False
    current_ma: int = 0
    at: str | None = None


@dataclass(frozen=True)
class PhoneTransition:
    kind: str
    snapshot: PhoneSnapshot
    session_id: str | None = None


class PhoneSessionStore:
    """Three consistent samples before a change; jitter creates no rows."""

    def __init__(
        self,
        repo: PhoneSessionRepository,
        *,
        debounce_samples: int = 3,
        purpose: str = "focus",
    ) -> None:
        self.repo = repo
        self.debounce_samples = max(1, int(debounce_samples))
        self.purpose = purpose
        self._samples: list[tuple[bool, bool]] = []
        self._stable = PhoneSnapshot()
        self._session_id: str | None = None
        self._last_transition: PhoneTransition | None = None
        open_session = repo.open_session()
        self._session_id = (
            str(open_session["id"]) if open_session is not None else None
        )

    @property
    def stable(self) -> PhoneSnapshot:
        return self._stable

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def last_transition(self) -> PhoneTransition | None:
        return self._last_transition

    def seed(self, snapshot: PhoneSnapshot) -> None:
        self._stable = snapshot
        self._samples.clear()

    def observe(
        self,
        present: bool,
        charging: bool,
        *,
        current_ma: int = 0,
        at: str | None = None,
    ) -> PhoneTransition | None:
        sample = (bool(present), bool(charging))
        self._samples.append(sample)
        self._samples = self._samples[-self.debounce_samples:]
        if len(self._samples) < self.debounce_samples:
            return None
        if len(set(self._samples)) != 1:
            return None
        snapshot = PhoneSnapshot(
            present=sample[0],
            charging=sample[1],
            current_ma=int(current_ma),
            at=at,
        )
        if (
            snapshot.present == self._stable.present
            and snapshot.charging == self._stable.charging
        ):
            self._stable = snapshot
            return None
        previous = self._stable
        self._stable = snapshot
        if snapshot.present and not previous.present:
            if self._session_id is None:
                self._session_id = self.repo.start(
                    purpose=self.purpose,
                    started_at=at,
                    present_state="charging" if charging else "placed",
                )
            transition = PhoneTransition(
                "placed",
                snapshot,
                self._session_id,
            )
        elif previous.present and not snapshot.present:
            if self._session_id is not None:
                self.repo.finish(self._session_id, ended_at=at)
                self._session_id = None
            transition = PhoneTransition("removed", snapshot)
        else:
            transition = PhoneTransition("charging", snapshot)
        self._last_transition = transition
        return transition

    def manual(
        self,
        present: bool,
        charging: bool = False,
        *,
        current_ma: int = 0,
        at: str | None = None,
    ) -> PhoneTransition | None:
        """Voice fallback: apply a user-reported state without sampling."""
        self._samples = [(bool(present), bool(charging))] * \
            self.debounce_samples
        return self.observe(
            present,
            charging,
            current_ma=current_ma,
            at=at,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "present": self._stable.present,
            "charging": self._stable.charging,
            "current_ma": self._stable.current_ma,
            "at": self._stable.at,
            "session_id": self._session_id,
            "last_transition": (
                self._last_transition.kind
                if self._last_transition is not None
                else None
            ),
        }
