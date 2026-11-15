"""Wire schemas. Bounds live here so validation happens at the boundary."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class WorkloadKind(str, Enum):
    mining = "mining"
    inference = "inference"
    training = "training"


class WorkloadState(str, Enum):
    queued = "queued"
    scheduled = "scheduled"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class WorkloadCreate(BaseModel):
    model_config = {"extra": "forbid"}  # unknown fields are errors, not silent drops

    kind: WorkloadKind
    region: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9-]+$")
    tier: Literal["shared", "dedicated"] = "shared"
    gpu_count: int = Field(default=1, ge=1, le=8)
    image: str = Field(min_length=3, max_length=255)
    duration_seconds: int = Field(default=600, ge=60, le=86_400)
    metadata: dict[str, str] = Field(default_factory=dict)


class Workload(BaseModel):
    id: str
    tenant_id: str
    kind: WorkloadKind
    region: str
    tier: str
    gpu_count: int
    image: str
    duration_seconds: int
    state: WorkloadState
    created_at: datetime
    updated_at: datetime
    receipt_id: str | None = None


class WorkloadPage(BaseModel):
    items: list[Workload]
    next_cursor: str | None = None


class Node(BaseModel):
    id: str
    region: str
    tier: str
    gpu_model: str
    gpu_count: int
    state: Literal["ready", "busy", "draining", "offline"]
    last_heartbeat: datetime


class NodePage(BaseModel):
    items: list[Node]
    next_cursor: str | None = None


class CapacitySlot(BaseModel):
    region: str
    tier: str
    free_slots: int


class Receipt(BaseModel):
    id: str
    workload_id: str
    tenant_id: str
    digest: str
    created_at: datetime


class Capability(BaseModel):
    id: str
    statement: str
    disposition: Literal["supported", "unverified", "withdrawn"]
    reviewer: str | None = None
    evidence: list[dict] = []
    notes: str | None = None


class Blocker(BaseModel):
    id: str
    description: str
    status: Literal["open", "closed"] = "open"


class Qualification(BaseModel):
    posture: Literal["qualified", "not_qualified"]
    reviewed_at: date
    commit: str
    counts: dict[str, int]
    blockers: list[Blocker]


class Lease(BaseModel):
    tenant_id: str
    tier: str
    entitlements: list[str]
    expires_at: datetime | None
    revoked: bool = False


class IntrospectionResult(BaseModel):
    tenant_id: str
    scopes: list[str]
    lease: Lease
