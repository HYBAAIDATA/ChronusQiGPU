"""Euclid Emergence Research Track: emergent_qualification_service (EQS) and Philos / Phi-2 framework."""

__version__ = "2.0.0"

from .models import (
    CapabilityManifest,
    NoveltyReport,
    TelemetryRecord,
    SubstrateProperties,
    SubstrateExecutionResult,
    DiscoveryEnvelope,
    ReproductionProtocol,
    EmergentCandidate,
    QualifiedEmergent,
    RejectedQualification,
    SuspendedQualification,
    COMPLEXITY_AXES,
    FORBIDDEN_ACTIONS,
    ColonyConfig,
    CondensationEvent,
    AdjudicationVerdict,
)
from .telemetry import (
    AgentTelemetry,
    TelemetryKeyManager,
    TelemetryRedactor,
    detect_novelty,
    TelemetryStream,
)
from .substrate import (
    SubstrateRegistry,
    SubstrateIndependenceVerifier,
    StandardSyncExecutor,
    AsyncIsolatedExecutor,
    RunHarness,
    TIER_1,
    TIER_5,
    TIER_15,
    TIER_20,
)
from .analyzer import EmergenceAnalyzer
from .trusted_core import (
    EmergentQualificationService,
    GovernanceToken,
    CallerBoundaryGuard,
    DivergenceMonitor,
    ImmutableEmergenceJournal,
)
from .cultivator import AgentColony, AgentColonies, CondensationCultivator
from .folding import (
    RecursiveFolding,
    FROZEN_MAX_FOLD,
    FROZEN_MAX_FOLD_SIGNATURE,
)
from .condensation import CondensationMonitor, ConsortiumGovernance

__all__ = [
    "CapabilityManifest",
    "NoveltyReport",
    "TelemetryRecord",
    "SubstrateProperties",
    "SubstrateExecutionResult",
    "DiscoveryEnvelope",
    "ReproductionProtocol",
    "EmergentCandidate",
    "QualifiedEmergent",
    "RejectedQualification",
    "SuspendedQualification",
    "COMPLEXITY_AXES",
    "FORBIDDEN_ACTIONS",
    "ColonyConfig",
    "CondensationEvent",
    "AdjudicationVerdict",
    "AgentTelemetry",
    "TelemetryKeyManager",
    "TelemetryRedactor",
    "detect_novelty",
    "TelemetryStream",
    "SubstrateRegistry",
    "SubstrateIndependenceVerifier",
    "StandardSyncExecutor",
    "AsyncIsolatedExecutor",
    "RunHarness",
    "TIER_1",
    "TIER_5",
    "TIER_15",
    "TIER_20",
    "EmergenceAnalyzer",
    "EmergentQualificationService",
    "GovernanceToken",
    "CallerBoundaryGuard",
    "DivergenceMonitor",
    "ImmutableEmergenceJournal",
    "AgentColony",
    "AgentColonies",
    "CondensationCultivator",
    "RecursiveFolding",
    "FROZEN_MAX_FOLD",
    "FROZEN_MAX_FOLD_SIGNATURE",
    "CondensationMonitor",
    "ConsortiumGovernance",
]
