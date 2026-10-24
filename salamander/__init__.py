"""#108 canonical Salamander autonomic control plane."""

from .control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    CircuitBreaker,
    EvidenceLedger,
    HealthEnvelope,
    RecoveryPlan,
)
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
from .authority import ALHarasActionAuthorizer, build_authorized_control_plane
from .models import *
# Mining integration is optional in the standalone control-plane distribution.
# Import it only when a mining export is explicitly requested.
_MINING_EXPORTS = frozenset({
    "HealActionAck", "HealAuditRecord", "HealDiagnosis", "HealObservation",
    "HealPostObservation", "HealerState", "SalamanderMiningHealer",
})


def __getattr__(name):
    if name in _MINING_EXPORTS:
        from importlib import import_module
        value = getattr(import_module(".mining_healer", __name__), name)
        globals()[name] = value
        return value
    if name == "AgentCapabilitySuite":
        from .agent_capabilities import AgentCapabilitySuite
        globals()[name] = AgentCapabilitySuite
        return AgentCapabilitySuite
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "ActionRegistry",
    "AgentCapabilitySuite",
    "ALHarasActionAuthorizer",
    "AutomationToolCategory",
    "BathtubAssessment",
    "BathtubGuard",
    "BathtubRiskFactor",
    "build_authorized_control_plane",
    "build_canonical_workflow_runbooks",
    "AutonomicControlPlane",
    "CircuitBreaker",
    "CollaborativeAutomationEngine",
    "CollaborativeRunbook",
    "CollaborativeStep",
    "CrossTeamTaskDeduplicator",
    "EvidenceLedger",
    "HealthEnvelope",
    "HumanDecision",
    "load_repository_catalogue_runbooks",
    "RecoveryPlan",
    "RunbookExecutionReport",
    "RunbookStatus",
    "SalamanderMiningHealer",
    "select_automation_tool",
    "StepMode",
    "StepStatus",
    "TeamRole",
    "ToolSelectionCriteria",
    "WorkflowUseCase",
    "HealActionAck",
    "HealAuditRecord",
    "HealDiagnosis",
    "HealObservation",
    "HealPostObservation",
    "HealerState",
]

__version__ = "1.0.0"
