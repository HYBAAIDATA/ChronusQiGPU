"""Exact action/resource/scope/purpose/limit/duration grants and logged denials."""

import threading
from dataclasses import dataclass
from enum import Enum
from ._contracts import ContractError, integer, text
from .trust import TrustLevel


class ActionKind(Enum):
    READ = "read"
    MODIFY = "modify"
    DISCLOSE = "disclose"
    PURCHASE = "purchase"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    DELETE = "delete"
    PUBLISH = "publish"


@dataclass(frozen=True)
class ActionRequest:
    id: str
    action: ActionKind
    resource: str
    scope: str
    purpose: str
    limit: int
    duration: int
    task_key: str
    data_sensitivity: str
    jurisdiction: str

    def __post_init__(self):
        if type(self.action) is not ActionKind:
            raise ContractError("typed action required")
        for value in (
            self.id,
            self.resource,
            self.scope,
            self.purpose,
            self.task_key,
            self.data_sensitivity,
            self.jurisdiction,
        ):
            text(value)
        integer(self.limit)
        integer(self.duration, minimum=1)
        if ".." in self.resource.split("/") or ".." in self.scope.split("/"):
            raise ContractError("permission paths cannot traverse")


@dataclass(frozen=True)
class PermissionTuple:
    id: str
    owner: str
    action: ActionKind
    resource: str
    scope: str
    purpose: str
    limit: int
    duration: tuple[int, int]
    task_key: str
    minimum_trust: TrustLevel

    def __post_init__(self):
        for value in (self.id, self.owner, self.resource, self.scope, self.purpose, self.task_key):
            text(value)
        if type(self.action) is not ActionKind or type(self.minimum_trust) is not TrustLevel:
            raise ContractError("typed grant required")
        integer(self.limit)
        if type(self.duration) is not tuple or len(self.duration) != 2:
            raise ContractError("explicit grant time window required")
        integer(self.duration[0])
        integer(self.duration[1], minimum=self.duration[0] + 1)
        if self.action != ActionKind.READ and self.minimum_trust < TrustLevel.ASSIST:
            raise ContractError("writes/effects require at least ASSIST")


class PermissionSet:
    def __init__(self, ledger):
        self.ledger = ledger
        self._lock = threading.RLock()
        self._grants = {}
        self._revoked = set()
        self._used = {}

    def grant(self, permission, *, now):
        with self._lock:
            if not isinstance(permission, PermissionTuple) or permission.id in self._grants:
                raise ContractError("invalid/duplicate host grant")
            self.ledger.append("permission_granted", permission, now=now, actor=permission.owner)
            self._grants[permission.id] = permission

    def revoke(self, grant_id, *, now):
        with self._lock:
            if grant_id not in self._grants:
                raise ContractError("unknown grant")
            self.ledger.append("permission_revoked", {"grant": grant_id}, now=now)
            self._revoked.add(grant_id)

    def permitted(self, request, *, level, now, consume=False):
        with self._lock:
            if not isinstance(request, ActionRequest) or type(level) is not TrustLevel:
                raise ContractError("typed request and current trust required")
            for p in self._grants.values():
                if (
                    p.id not in self._revoked
                    and p.action == request.action
                    and p.resource == request.resource
                    and p.scope == request.scope
                    and p.purpose == request.purpose
                    and p.task_key == request.task_key
                    and level >= p.minimum_trust
                    and p.duration[0] <= now
                    and now + request.duration <= p.duration[1]
                    and self._used.get(p.id, 0) + request.limit <= p.limit
                ):
                    if consume:
                        self._used[p.id] = self._used.get(p.id, 0) + request.limit
                    return True
            self.ledger.append(
                "permission_denied",
                request,
                now=now,
                rationale="six-tuple/trust/expiry/usage mismatch",
            )
            return False
