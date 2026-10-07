"""HYBA's six-layer, tenant-scoped, attested ontology store."""

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
    "OvidTransformPlane",
    "OntologyStoreError",
    "ProofStatus",
    "Quota",
    "QuotaExceeded",
    "ReconciliationReport",
    "TensorRecord",
    "TheseusFileCustody",
]
