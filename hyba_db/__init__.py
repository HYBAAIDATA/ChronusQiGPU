"""Tenant-scoped OVID data organisation over THESEUS durable custody."""

from .models import (
    AccessDenied,
    Attestation,
    Certificate,
    Client,
    DatabaseVerification,
    EdgeRecord,
    FoldRecord,
    IntegrityFailure,
    InvalidRecord,
    NodeRecord,
    OntologyStoreError,
    Quota,
    QuotaExceeded,
    TensorRecord,
)
from .file_registry import FileRegistry, ReconciliationReport
from .knowledge import KnowledgeProjection, KnowledgeRecord
from .module_adapter import ModuleEvidenceAdapter
from .ovid_transform import OvidTransformPlane
from .ovid_index import OvidDataIndex, OvidIndexEntry
from .store import EdgeKind, NodeKind, OntologyStore, ProofStatus
from .theseus_custody import TheseusFileCustody

__all__ = [
    "AccessDenied",
    "Attestation",
    "Certificate",
    "Client",
    "DatabaseVerification",
    "EdgeKind",
    "EdgeRecord",
    "FileRegistry",
    "FoldRecord",
    "IntegrityFailure",
    "KnowledgeProjection",
    "KnowledgeRecord",
    "InvalidRecord",
    "ModuleEvidenceAdapter",
    "NodeKind",
    "OntologyStore",
    "OvidDataIndex",
    "OvidIndexEntry",
    "OvidTransformPlane",
    "OntologyStoreError",
    "ProofStatus",
    "Quota",
    "QuotaExceeded",
    "ReconciliationReport",
    "TensorRecord",
    "TheseusFileCustody",
]
