"""Canonical PYTHIA mining subsystem.

This package contains the deterministic solver, measured intelligence,
Turing-derived ordering, M32 routing, observed-block verification, the exact
Stratum proof adapter, and the SHA256d proof boundary.
"""

from .cassini_seal import InvalidCassiniSeal, compute_seal, verify_seal
from .chooser import MiningIntelligenceChooser, SearchDecision, SearchPolicy
from .lane import FLAT_STRUCTURE_PRIOR, M32_STRUCTURE_PRIOR, build_lane_descriptor
from .execution import MiningExecutionResult
from .geometry import (
    M32GovernanceError,
    M32Topology,
    PhyllotaxisLaneIndex,
    spherical_design_moments,
    truncated_icosahedron_frame,
    verify_spherical_design,
)
from .hyba_bridge import (
    AVAILABLE as HYBA_CORE_AVAILABLE,
    describe_share,
    face_of,
    measure_window,
    resonance_of,
)
from .intelligence_controller import (
    ControlCommand,
    ControlSignal,
    ControllerDecision,
    IntelligenceController,
)
from .opencl_driver import OpenCLDevice, OpenCLDriver, OpenCLExecutionResult, OpenCLUnavailable
from .persistence import BackpressureRequired, CorruptRecord, PrimeDBPersistence, TelemetryCounters
from .self_optimizing_agent import (
    ExclusionCertificate,
    OptimizationObservation,
    OptimizationRejected,
    SelfOptimizingTuner,
    SchedulePlan,
    WorkGroupPlan,
)
from .self_healing_agent import (
    NonBlockingRecoveryQueue,
    RecoveryAction,
    RecoveryBackpressure,
    RecoveryCommand,
    RecoveryPlan,
    SelfHealingAgent,
)
from .toe_context import ObservedTransition, TOEContext, TOEContextBuilder, TOEContextUnavailable
from .pow import (
    LUCAS_EXECUTION_SCALE_INDICES,
    LucasScaleError,
    build_header,
    check_pow,
    compact_target,
    require_lucas_execution_scale,
    sha256d,
)
from .solver import M32SearchSolver, SolveResult
from .stratum_adapter import (
    CassiniSealError,
    ProofCheckedCandidate,
    StaleJobError,
    StratumAdapterError,
    StratumJob,
    StratumProofAdapter,
    SubscriptionState,
    TargetError,
)
from .turing_adapter import (
    TuringCoreUnavailable,
    TuringMiningSubstrate,
    TuringScheduleEvidence,
)
from .verification import BlockVerification, verify_block_record

__all__ = [
    "MiningIntelligenceChooser",
    "SearchDecision",
    "SearchPolicy",
    "MiningExecutionResult",
    "InvalidCassiniSeal",
    "compute_seal",
    "verify_seal",
    "ControlCommand",
    "ControlSignal",
    "ControllerDecision",
    "IntelligenceController",
    "OpenCLDevice",
    "OpenCLDriver",
    "OpenCLExecutionResult",
    "OpenCLUnavailable",
    "BackpressureRequired",
    "CorruptRecord",
    "PrimeDBPersistence",
    "TelemetryCounters",
    "ExclusionCertificate",
    "OptimizationObservation",
    "OptimizationRejected",
    "SelfOptimizingTuner",
    "SchedulePlan",
    "WorkGroupPlan",
    "NonBlockingRecoveryQueue",
    "RecoveryAction",
    "RecoveryBackpressure",
    "RecoveryCommand",
    "RecoveryPlan",
    "SelfHealingAgent",
    "ObservedTransition",
    "TOEContext",
    "TOEContextBuilder",
    "TOEContextUnavailable",
    "M32SearchSolver",
    "SolveResult",
    "BlockVerification",
    "TuringCoreUnavailable",
    "TuringMiningSubstrate",
    "TuringScheduleEvidence",
    "M32_STRUCTURE_PRIOR",
    "FLAT_STRUCTURE_PRIOR",
    "build_lane_descriptor",
    "build_header",
    "check_pow",
    "compact_target",
    "sha256d",
    "LUCAS_EXECUTION_SCALE_INDICES",
    "LucasScaleError",
    "require_lucas_execution_scale",
    "M32GovernanceError",
    "M32Topology",
    "PhyllotaxisLaneIndex",
    "spherical_design_moments",
    "truncated_icosahedron_frame",
    "verify_spherical_design",
    "verify_block_record",
    "CassiniSealError",
    "ProofCheckedCandidate",
    "StaleJobError",
    "StratumAdapterError",
    "StratumJob",
    "StratumProofAdapter",
    "SubscriptionState",
    "TargetError",
    "HYBA_CORE_AVAILABLE",
    "describe_share",
    "face_of",
    "measure_window",
    "resonance_of",
]
