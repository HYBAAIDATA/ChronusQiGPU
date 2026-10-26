"""#108 canonical Salamander autonomic control plane."""

from __future__ import annotations

from .authority import ALHarasActionAuthorizer, build_authorized_control_plane
from .collaborative_automation import (
    AutomationToolCategory,
    BathtubAssessment,
    BathtubGuard,
    BathtubRiskFactor,
    CollaborativeAutomationEngine,
    CollaborativeRunbook,
    CollaborativeStep,
    CrossTeamTaskDeduplicator,
    HumanDecision,
    RunbookExecutionReport,
    RunbookStatus,
    StepMode,
    StepStatus,
    TeamRole,
    ToolSelectionCriteria,
    WorkflowUseCase,
    build_canonical_workflow_runbooks,
    load_repository_catalogue_runbooks,
    select_automation_tool,
)
from .control_plane import (
    EVIDENCE_SCHEMA,
    SCHEMA,
    ActionRegistry,
    AutonomicControlPlane,
    CircuitBreaker,
    EvidenceLedger,
    FailClosed,
    HealthEnvelope,
    RecoveryPlan,
    RecoveryStep,
)
from .models import *
from .runtime import (
    ActionClass,
    CustodiedMiningOutcomeVerifier,
    DurableEvidenceLedger,
    FaultClass,
    MiningAutonomyBridge,
    OutcomeVerification,
    unqualified_readiness,
)

# Mining and discovery integration are optional in the standalone distribution.
# Import them only when explicitly requested.
_MINING_EXPORTS = frozenset({
    "HealActionAck",
    "HealAuditRecord",
    "HealDiagnosis",
    "HealObservation",
    "HealPostObservation",
    "HealerState",
    "SalamanderMiningHealer",
})

_DISCOVERY_EXPORTS = frozenset({
    "DiscoveryOptimisationBridge",
    "DiscoveryOptimisationCandidate",
    "DiscoveryRefused",
})


def __getattr__(name: str):
    if name in _MINING_EXPORTS:
        from importlib import import_module
        value = getattr(import_module(".mining_healer", __name__), name)
        globals()[name] = value
        return value
    if name in _DISCOVERY_EXPORTS:
        from importlib import import_module
        value = getattr(import_module(".discovery_optimisation", __name__), name)
        globals()[name] = value
        return value
    if name == "AgentCapabilitySuite":
        from .agent_capabilities import AgentCapabilitySuite
        globals()[name] = AgentCapabilitySuite
        return AgentCapabilitySuite
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))


__version__ = "1.0.0"

__all__ = sorted([
    "ALHarasActionAuthorizer",
    "ActionClass",
    "ActionKind",
    "ActionRegistry",
    "ActionRequest",
    "ActionResult",
    "ActionVerification",
    "Admission",
    "AdmissionDecision",
    "AgentCapabilitySuite",
    "AuthorityClass",
    "AutomationToolCategory",
    "AutonomicControlPlane",
    "AutonomicEvent",
    "Availability",
    "BackendLifecycle",
    "BathtubAssessment",
    "BathtubGuard",
    "BathtubRiskFactor",
    "CapabilityIdentity",
    "CapabilityState",
    "ChronusHealthEnvelope",
    "CircuitBreaker",
    "CircuitState",
    "CollaborativeAutomationEngine",
    "CollaborativeRunbook",
    "CollaborativeStep",
    "CrossTeamTaskDeduplicator",
    "CustodiedMiningOutcomeVerifier",
    "DatasetPartition",
    "DiscoveryOptimisationBridge",
    "DiscoveryOptimisationCandidate",
    "DiscoveryRefused",
    "DurableEvidenceLedger",
    "EVIDENCE_SCHEMA",
    "EvidenceLedger",
    "FailClosed",
    "FaultClass",
    "HealActionAck",
    "HealAuditRecord",
    "HealDiagnosis",
    "HealObservation",
    "HealPostObservation",
    "HealerState",
    "HealthDecision",
    "HealthEnvelope",
    "HealthObservation",
    "HealthState",
    "HumanDecision",
    "LearningExperience",
    "MiningAutonomyBridge",
    "OptimizationTrial",
    "OutcomeVerification",
    "OvidTransformEvidence",
    "PolicyLifecycle",
    "PolicyVersion",
    "RebuildableProjection",
    "RecoveryPlan",
    "RecoveryStep",
    "RewardAuthority",
    "RunbookExecutionReport",
    "RunbookStatus",
    "SCHEMA",
    "SalamanderMiningHealer",
    "Severity",
    "StepMode",
    "StepStatus",
    "TeamRole",
    "TheseusRecordIdentity",
    "ToolSelectionCriteria",
    "WorkflowUseCase",
    "build_authorized_control_plane",
    "build_canonical_workflow_runbooks",
    "canonical",
    "digest",
    "load_repository_catalogue_runbooks",
    "select_automation_tool",
    "unqualified_readiness",
])
