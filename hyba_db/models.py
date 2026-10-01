"""Public immutable records for the HYBA ontology store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class OntologyStoreError(RuntimeError):
    """Base error for ontology-store failures."""


class AccessDenied(OntologyStoreError):
    """A record was requested outside the caller's tenant namespace."""


class QuotaExceeded(OntologyStoreError):
    """A write would exceed the tenant's declared quota."""


class IntegrityFailure(OntologyStoreError):
    """A digest, certificate, graph or attestation invariant failed."""


class InvalidRecord(OntologyStoreError):
    """A caller supplied a record outside the schema contract."""


@dataclass(frozen=True)
class Quota:
    max_records: int
    max_blob_bytes: int

    def __post_init__(self) -> None:
        if self.max_records < 1 or self.max_blob_bytes < 0:
            raise InvalidRecord("quota limits must be positive")


@dataclass(frozen=True)
class Client:
    tenant_id: str
    namespace: str
    quota: Quota
    root_attestation_id: str
    root_node_id: str
    created_at: str


@dataclass(frozen=True)
class Attestation:
    id: str
    tenant_id: str
    subject: str
    issuer: str
    signature: str
    timestamp: str
    sequence: int
    chain_root: str
    parents: tuple[str, ...]
    details: dict[str, Any]


@dataclass(frozen=True)
class Certificate:
    id: str
    tenant_id: str
    masks: tuple[int, ...]
    digest: str
    vector_digest: str
    lucas: tuple[int, ...]
    depth: int
    scale: int
    attestation_id: str


@dataclass(frozen=True)
class FoldRecord:
    id: str
    tenant_id: str
    vector: tuple[float, ...]
    certificate: Certificate
    parent_id: str | None
    created_at: str
    attestation_id: str


@dataclass(frozen=True)
class TensorRecord:
    id: str
    tenant_id: str
    kind: str
    fold_id: str
    payload: bytes
    format: str
    dimensions: tuple[int, ...]
    norm: float
    entropy: float | None
    trace: float | None
    invariants: dict[str, Any]
    digest: str
    attestation_id: str
    created_at: str


@dataclass(frozen=True)
class NodeRecord:
    id: str
    tenant_id: str
    kind: str
    payload: dict[str, Any]
    betti: tuple[int, ...] | None
    persistence: float | None
    attestation_id: str
    created_at: str


@dataclass(frozen=True)
class EdgeRecord:
    id: str
    tenant_id: str
    from_node: str
    to_node: str
    kind: str
    weight: float
    attestation_id: str
    created_at: str


@dataclass(frozen=True)
class DatabaseVerification:
    foreign_keys_ok: bool
    attestations_ok: bool
    certificates_ok: bool
    fold_dag_ok: bool
    tenant_usage_ok: bool
    graph_connected: bool
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.errors
