"""#108 canonical Salamander autonomic control plane."""

from .control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    CircuitBreaker,
    EvidenceLedger,
    HealthEnvelope,
    RecoveryPlan,
)
from .authority import ALHarasActionAuthorizer, build_authorized_control_plane
from .models import *
from .mining_healer import (
    HealActionAck,
    HealAuditRecord,
    HealDiagnosis,
    HealObservation,
    HealPostObservation,
    HealerState,
    SalamanderMiningHealer,
)

__all__ = [
    "ActionRegistry",
    "ALHarasActionAuthorizer",
    "build_authorized_control_plane",
    "AutonomicControlPlane",
    "CircuitBreaker",
    "EvidenceLedger",
    "HealthEnvelope",
    "RecoveryPlan",
    "SalamanderMiningHealer",
    "HealActionAck",
    "HealAuditRecord",
    "HealDiagnosis",
    "HealObservation",
    "HealPostObservation",
    "HealerState",
]

__version__ = "1.0.0"