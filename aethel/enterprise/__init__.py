"""Enterprise Chronus·Theseus·Ovid custody substrate (single-root software).

Claim scope: enterprise_custody_software_single_root — measured local custody.
Not a distributed hyperscaler.
"""
from __future__ import annotations

from .adapters import (
    CLASSIFICATION_REGISTRY,
    StoreClass,
    StoreClassification,
    classification_report,
    classify,
    mirror_digest,
    wrap_notes,
)
from .authenticity import (
    CustodyKey,
    content_digest,
    is_insecure_dev_key,
    mac_create,
    mac_verify,
)
from .custody import EnterpriseCustody, EnterpriseTheseus, compose
from .errors import (
    AuthenticityError,
    AuthorityBoundaryError,
    ConcurrencyConflict,
    EnterpriseCustodyError,
    ReadOnlyModeError,
    ResourceExhausted,
    SchemaVersionError,
    UnrecoverableCustodyError,
)
from .governance import Quotas
from .hooks import (
    AlHarasEvidenceAdapter,
    AllowAllHook,
    DenyingHook,
    SecurityHook,
)
from .journal import FileLock, WriteAheadJournal
from .lifecycle import CompositionRoot
from .ovid_registry import DEFAULT_OVID_REGISTRY, OvidRegistry
from .parity import assert_cpu_accel_parity
from .schema import (
    OVID_TRANSFORM_V1,
    THESEUS_FORMAT_VERSION,
    CustodyEnvelope,
    CustodyEvent,
    canonical_manifest_bytes,
)
from .telemetry import EvidenceTelemetry

__all__ = [
    # custody
    "EnterpriseCustody",
    "EnterpriseTheseus",
    "compose",
    "CompositionRoot",
    # schema
    "THESEUS_FORMAT_VERSION",
    "OVID_TRANSFORM_V1",
    "CustodyEnvelope",
    "CustodyEvent",
    "canonical_manifest_bytes",
    # errors
    "EnterpriseCustodyError",
    "AuthorityBoundaryError",
    "UnrecoverableCustodyError",
    "ResourceExhausted",
    "ConcurrencyConflict",
    "SchemaVersionError",
    "AuthenticityError",
    "ReadOnlyModeError",
    # auth
    "content_digest",
    "mac_create",
    "mac_verify",
    "CustodyKey",
    "is_insecure_dev_key",
    # support
    "Quotas",
    "EvidenceTelemetry",
    "FileLock",
    "WriteAheadJournal",
    "SecurityHook",
    "AllowAllHook",
    "DenyingHook",
    "AlHarasEvidenceAdapter",
    "OvidRegistry",
    "DEFAULT_OVID_REGISTRY",
    "assert_cpu_accel_parity",
    "StoreClass",
    "StoreClassification",
    "CLASSIFICATION_REGISTRY",
    "classify",
    "wrap_notes",
    "mirror_digest",
    "classification_report",
]
