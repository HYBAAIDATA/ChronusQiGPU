"""One security check for every platform action. Unknown actors are denied."""

from __future__ import annotations


class AccessDenied(PermissionError):
    pass


ROLES = {
    "reader": frozenset({"ask", "export", "health"}),
    "analyst": frozenset({"ask", "export", "health", "train", "predict", "dashboard"}),
    "operator": frozenset({"ask", "export", "health", "train", "predict", "dashboard", "connect", "ingest", "heal"}),
    "admin": frozenset({"ask", "export", "health", "train", "predict", "dashboard", "connect", "ingest", "heal", "grant", "reload"}),
}


class SecurityModel:
    def __init__(self) -> None:
        self.enforced = False
        self._roles: dict[str, str] = {}
        self.actor = "anonymous"

    def grant(self, name: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role {role}")
        self._roles[name] = role

    def authenticate(self, name: str) -> None:
        self.actor = name

    def authorize(self, action: str) -> None:
        if not self.enforced:
            return
        role = self._roles.get(self.actor)
        if role is None or action not in ROLES[role]:
            raise AccessDenied(f"{self.actor} cannot {action}")
