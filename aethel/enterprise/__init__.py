"""Enterprise Chronus·Theseus·Ovid custody substrate.

Claim scopes (Rule 7 — honest software measurement):
  - enterprise_custody_software_single_root
  - distributed_consensus_software_multi_node_local
  - multi_root_multi_node_custody_software
  - cross_region_dr_software_simulated_regions
  - hyperscaler_soak_software_local_fleet
  - chronus_hardware_perf_measured
  - solutions_api_readiness_software
  - enterprise_hyba_certification_gate_software

Not a vendor cloud fleet; not real multi-region WAN.
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
from .checkpoint import (
    CheckpointIntegrityError,
    CheckpointManager,
    CheckpointUnavailableError,
)
from .custody import EnterpriseCustody, EnterpriseTheseus, compose
from .distributed import (
    ChronusPerfProbe,
    ClusterTransport,
    CrossRegionDR,
    HybaEnterpriseCertificate,
    HyperscalerSoak,
    LogEntry,
    MultiNodeCluster,
    MultiRootCustody,
    NodeId,
    PerfReport,
    RaftNode,
    SoakReport,
    SolutionsAPI,
)
from .entangled_custody import (
    BINDING_SCHEMA,
    CANONICAL_DATA_SYSTEMS,
    SCHEMA as ENTANGLED_CUSTODY_SCHEMA,
    EntangledAccessError,
    EntangledCustodyError,
    EntangledCustodyFabric,
    EntanglementBinding,
    SystemDataPort,
)
from .errors import (
    AuthenticityError,
    AuthorityBoundaryError,
    CertificationError,
    ConcurrencyConflict,
    ConsensusError,
    EnterpriseCustodyError,
    NotLeaderError,
    QuorumLostError,
    ReadOnlyModeError,
    RegionFailoverError,
    ResourceExhausted,
    SchemaVersionError,
    SoakThresholdError,
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
from .records import (
    CANONICAL_PRODUCERS,
    DEPENDENCY_OVID_TRANSFORM,
    DEPENDENCY_THESEUS_FORMAT,
    EVIDENCE_STATES,
    ContractValidationError,
    DependencyMismatchError,
    OperationalRecord,
    ProducerAdmissionError,
    ProducerContract,
    ProducerRegistry,
    default_dependency_policy,
    default_producer_registry,
)
from .recovery import RecoveryReport
from .retention import RetentionPolicy
from .schema import (
    OVID_TRANSFORM_V1,
    THESEUS_FORMAT_VERSION,
    CustodyEnvelope,
    CustodyEvent,
    canonical_manifest_bytes,
)
from .system_relations import (
    DEFAULT_PEERS,
    ProductionSystemRelations,
    SharedALHaras,
    SharedEuclid,
    SharedKellogg,
    SharedPythiaStore,
    SharedSalamander,
    SharedTOEBridge,
    SharedTuring,
)
from .telemetry import EvidenceTelemetry

__all__ = [
    # custody
    "EnterpriseCustody",
    "EnterpriseTheseus",
    "compose",
    "CompositionRoot",
    # shared THESEUS / OVID data entanglement
    "ENTANGLED_CUSTODY_SCHEMA",
    "BINDING_SCHEMA",
    "CANONICAL_DATA_SYSTEMS",
    "EntangledCustodyError",
    "EntangledAccessError",
    "EntanglementBinding",
    "SystemDataPort",
    "EntangledCustodyFabric",
    # live subsystem bindings over the shared fabric
    "DEFAULT_PEERS",
    "ProductionSystemRelations",
    "SharedPythiaStore",
    "SharedTOEBridge",
    "SharedSalamander",
    "SharedALHaras",
    "SharedKellogg",
    "SharedTuring",
    "SharedEuclid",
    # distributed / multi-root / DR / soak / API / cert
    "NodeId",
    "LogEntry",
    "RaftNode",
    "ClusterTransport",
    "MultiNodeCluster",
    "MultiRootCustody",
    "CrossRegionDR",
    "HyperscalerSoak",
    "SoakReport",
    "ChronusPerfProbe",
    "PerfReport",
    "SolutionsAPI",
    "HybaEnterpriseCertificate",
    # schema
    "THESEUS_FORMAT_VERSION",
    "OVID_TRANSFORM_V1",
    "CustodyEnvelope",
    "CustodyEvent",
    "canonical_manifest_bytes",
    # operational records / checkpoints / recovery / retention
    "OperationalRecord",
    "ProducerContract",
    "ProducerRegistry",
    "ProducerAdmissionError",
    "ContractValidationError",
    "DependencyMismatchError",
    "EVIDENCE_STATES",
    "CANONICAL_PRODUCERS",
    "DEPENDENCY_THESEUS_FORMAT",
    "DEPENDENCY_OVID_TRANSFORM",
    "default_producer_registry",
    "default_dependency_policy",
    "CheckpointManager",
    "CheckpointIntegrityError",
    "CheckpointUnavailableError",
    "RecoveryReport",
    "RetentionPolicy",
    # errors
    "EnterpriseCustodyError",
    "AuthorityBoundaryError",
    "UnrecoverableCustodyError",
    "ResourceExhausted",
    "ConcurrencyConflict",
    "SchemaVersionError",
    "AuthenticityError",
    "ReadOnlyModeError",
    "ConsensusError",
    "NotLeaderError",
    "QuorumLostError",
    "RegionFailoverError",
    "SoakThresholdError",
    "CertificationError",
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
