"""Typed AL HARAS request and verdict contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
import time
import uuid


@dataclass(frozen=True)
class GuardianRequest:
    tenant_id: str
    operation: str
    resource: str
    payload: Mapping[str, Any]
    actor: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    observed_at: int = field(default_factory=lambda: int(time.time()))

    def __post_init__(self) -> None:
        for name in ("tenant_id", "operation", "resource", "actor", "request_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")


@dataclass(frozen=True)
class GuardianVerdict:
    allowed: bool
    reason: str
    evidence_id: str
    tenant_id: str
    operation: str
    payload_hash: str
    evaluated_at: int
    subscription_id: str | None
    policy_version: str
    intelligence_evidence_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Admission:
    request: GuardianRequest
    subscription_id: str
    payload_hash: str
    evaluated_at: int