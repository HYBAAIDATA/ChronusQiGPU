"""One security check for every platform action. Unknown actors are denied."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock


class AccessDenied(PermissionError):
    pass


ROLES = {
    "reader": frozenset({"ask", "export", "health"}),
    "analyst": frozenset({"ask", "export", "health", "train", "predict", "dashboard"}),
    "operator": frozenset(
        {
            "ask",
            "export",
            "health",
            "train",
            "predict",
            "dashboard",
            "connect",
            "ingest",
            "heal",
            "operate",
        }
    ),
    "admin": frozenset(
        {
            "ask",
            "export",
            "health",
            "train",
            "predict",
            "dashboard",
            "connect",
            "ingest",
            "heal",
            "grant",
            "reload",
            "govern",
            "operate",
        }
    ),
}


class SecurityModel:
    def __init__(self, *, enforced: bool = False) -> None:
        self.enforced = enforced
        self._lock = RLock()
        self._roles: dict[str, str] = {}
        self._actor: ContextVar[str] = ContextVar("unified_actor", default="anonymous")

    @property
    def actor(self) -> str:
        return self._actor.get()

    @actor.setter
    def actor(self, name: str) -> None:
        self._actor.set(name)

    def grant(self, name: str, role: str) -> None:
        with self._lock:
            # Bootstrap is a trusted embedding operation, not public registration.
            if self.enforced and self._roles:
                self.authorize("grant")
            if role not in ROLES:
                raise ValueError(f"unknown role {role}")
            self._roles[name] = role

    def authenticate(self, name: str) -> None:
        """Select an identity already authenticated by the trusted embedding host.

        This does not verify credentials. Never expose it as a login endpoint.
        Identity is local to the current thread/async context, not process-global.
        """
        self.actor = name

    @contextmanager
    def as_actor(self, name: str):
        """Temporarily select a trusted host identity; always restore the caller."""
        token = self._actor.set(name)
        try:
            yield
        finally:
            self._actor.reset(token)

    def authorize(self, action: str) -> None:
        if not self.enforced:
            return
        with self._lock:
            role = self._roles.get(self.actor)
            if role is None or action not in ROLES[role]:
                raise AccessDenied(f"{self.actor} cannot {action}")
