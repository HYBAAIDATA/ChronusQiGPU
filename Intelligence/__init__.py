"""EUCLID-CORE Intelligence package.

This is the central intelligence layer of the repo. It wires together every
intelligence module that was added to the project — the AGI substrates
(formerly ``core_engine``), the five TOE intelligences (consumed from the
``toe`` package), the consciousness measurement modules, the Salamander
self-healing / self-optimising autonomy plane, the ``asi`` attribute
framework, the ``quantum_cuda`` iGPU / Turing accelerator, and the
``experiments`` golden-transform test programme — and exposes them as a
single mining-front-and-centre orchestrator.

Design intent
-------------
The repo's thesis is that intelligence can *emerge from complexity*. This
package introduces that complexity (the layered AGI substrate, the
gauge-invariant distributed training, the spectral / topological context, the
exact Q[√5] quantum-math accelerator) in one place, and then offers a
falsifiable test for whether intelligence actually emerged from it.

The orchestrator does **not** fabricate intelligence. Every capability
reports an honest confidence: when the underlying substrate cannot service a
request the confidence is 0.0, so downstream callers can distinguish a real
result from a placeholder.

Public surface
--------------
- :class:`IntelligenceOrchestrator` — the central mining intelligence layer.
- :func:`get_intelligence` — process-wide singleton accessor.
- :func:`wire_intelligence_into_mining` — attach intelligence to the Pythia
  mining engine so every mining step is intelligence-guided.
- :func:`run_intelligence_self_test` — falsifiable emergence test.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Ensure the project root is importable for turing_core / core_engine / src.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger("Intelligence")

from .registry import ModuleRegistry
from .orchestrator import IntelligenceOrchestrator, MiningIntelligenceResult
from .mining_bridge import (
    wire_intelligence_into_mining,
    unwire_intelligence_from_mining,
)
from .self_test import run_intelligence_self_test
from .pythia_learning import PythiaLearning, LearningResult, LearnedPattern
from .pythia_memory import (
    PythiaMemorySystem,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    ArchivalMemory,
    CognitiveScaffolding,
    SocraticFeedbackLoop,
    MetaCognitiveReflection,
)
from .agentic_controller import (
    AgenticController,
    PolyhedralMapping,
    SolverType,
    LandscapeType,
)
from .lucas_scales import (
    LucasScaleProfile,
    LucasScaleLevel,
    build_lucas_scale_profile,
    multiscale_coherence_probe,
    LUCAS_SCALE_LADDER,
    SCALE_ORDER,
)
from .safety_constraints import (
    SafetyController,
    MiningState,
    HashrateCapEnforcer,
    ConsecutiveBlockGuard,
)
from .predictive_solver import PredictiveSolver, PredictionResult
from .counterfactual_intelligence import (
    CounterfactualIntelligence,
    IntelligenceModality,
    Manifold11D,
    project_to_11d,
)
from .hardware_config import (
    HardwareProfile,
    detect_hardware_profile,
    get_hardware_profile,
    reset_hardware_profile,
)
from .pythia_knowledge import seed_memory as seed_pythia_knowledge, KNOWLEDGE_FACTS
from .pythia_tools import seed_tool_knowledge, get_tool_summary, PythiaTool, TOOLS
from .skill_loader import (
    seed_skill_knowledge,
    get_skill_summary,
    PythiaSkill,
    discover_skills,
)
from .requirements import AGIASIRequirements, RequirementsReport, SchoolVerdict
from .pde_substrate import (
    PenroseOrchOR,
    IntegratedInformation,
    GlobalWorkspace,
    FreeEnergyPrinciple,
)
from toe.bridge import (
    TOEBridge,
    TOEStateTomography,
    TOETrajectoryPrediction,
    TOECausalAnalysis,
    CausalLadderResult,
    create_toe_bridge,
)
from toe.causal_ladder import (
    CausalGraph,
    StructuralCausalModel,
    infer_causal_graph,
    do_operator,
    counterfactual_query,
    identify_backdoor,
    identify_frontdoor,
)
from .salamander import (
    SalamanderEngine,
    HomeostasisMonitor,
    HomeostasisReport,
    SelfRepairEngine,
    RepairProposal,
    CircuitBreaker,
    LucasIntelligenceScaler,
    LucasScaleResult,
    AllocationSlot,
    SalamanderPoincareAllocationManager,
    AllocationManager,
    SelfHealingLoop,
    FaultRecord,
    AutonomySupervisor,
    CassiniCycleLedger,
    KNOWN_FAULT_TYPES,
)
from .autonomous_capabilities import (
    CuopMeter,
    CuopReading,
    CuopLearner,
    SelfOptimisingLoop,
    ValidityLearner,
    CoolDownController,
    telemetry_snapshot,
    cassini_fingerprint,
)
from toe.poincare_golden_11d import (
    PHI,
    PSI,
    INV_PHI,
    PHI_SQ,
    PHI_POWERS,
    LUCAS_TABLE,
    FIB_TABLE,
    PRIME_BUCKETS,
    compute_poincare_norm_sq,
    poincare_golden_distance,
    fold_poincare_11d_vector,
    unfold_poincare_11d_vector,
    ZeckendorfCertificate,
    compute_zeckendorf_certificate,
    generate_zeckendorf_decoupling_mask,
    resolve_zeckendorf_slot,
    encode_zeckendorf,
    beatty_partition,
    cassini_unimodular_det,
    get_metallic_mean,
)
from .orchestrator import (
    UniversalPassportToken,
    DecisionGateViolationError,
    verify_passport_hard_gate,
)
from kellogg.quantum_tensor import (
    Complex,
    ComplexMatrix,
    QuantumState,
    Observables,
    quantum_fisher_information,
    encode_data_to_state,
    state_tomography,
    path_integral_propagate,
    trajectory_forecast,
    causal_factor_ranking,
    born_probabilities,
    density_matrix_purity,
    decoherence_measure,
    model_agreement_from_ensemble,
    project_to_32_face,
    effective_subspace_dimension,
)
from .backend_binding import (
    BackendBinder,
    BackendDetector,
    BackendType,
    BoundBackend,
    GPUUnavailableError,
    get_compute_backend,
    reset_compute_backend,
)
from .neural_plasticity import (
    NeuralPlasticity,
    PlasticSynapse,
    PlasticityEvent,
)
from .neural_plasticity_integration import PlasticUnifiedRuntime
from .neural_plasticity_quantum import QuantumPlasticity
from .apple_features import (
    AppleSiliconDetector,
    AppleSiliconInfo,
    AppleNeuralEngine,
    AppleMetal,
    AppleAccelerate,
    AppleUnifiedMemory,
    AppleSiliconRuntime,
)
from .apple_plasticity import ApplePlasticity
from .pvsnp_memory import (
    LucasQuantumMemory,
    UnlimitedQuantumStore,
    PVsNPMemoryProof,
    PVsNPGPU,
    QuantumGPU,
)
from .prime_memory import (
    PrimeMemory,
    ExponentialPrimeStore,
    QuantumPrimeMemory,
)

# Consolidated intelligence modules (moved in from core_engine / legacy).
from .agi_substrate import (
    AGICapability,
    AGIDegradationMode,
    AGIRequest,
    AGIResponse,
    AGITelemetry,
    CanonicalAGISubstrate,
    create_canonical_agi_substrate,
)
from .layered_intelligence_substrate import (
    AGISubstrate,
    IntelligenceLayer,
    IntelligenceState,
)
from .nobel_fields_intelligence import (
    MathematicalDomain,
    MathematicalInsight,
    NobelFieldsIntelligence,
)
from . import asi, consciousness, self_healing
from .consciousness import (
    ConsciousnessEngine,
    ConsciousnessLevel,
    ConsciousnessStateVector,
    EmergenceMetrics,
    EmergenceSnapshot,
    QuantumConsciousnessSystem,
    QuantumPattern,
    SchoolActivity,
)
from .self_healing import (
    AutopoieticMetaOptimizer,
    CircuitState,
    LedgerLoadError,
    SalamanderFailureBus,
    SalamanderHardwareSmoother,
    SalamanderWiringInspector,
    SalamanderZeroTrustGovernor,
    SelfRepairCycleReport,
    StartupSelfHealingState,
    TuningRecommendation,
    VeritasLedger,
    get_startup_self_healing_state,
    run_self_repair_cycle,
    start_startup_self_healing,
)

# Aethel topological storage substrate — wired in with measured CPU/memory
# overhead accounting (aethel.costs). aethel's reverse imports into this
# package (pathfinder, search_crystal) are lazy, so eager import is safe.
from aethel import (
    AddressSpace,
    AethelQueue,
    CassiniLedger,
    FibonacciAddress,
    LedgerEntry,
    PrimeStorageManifold,
    UnifiedSubstrate,
)
from aethel.costs import (
    OpCost,
    OverheadMeter,
    container_bytes,
    measure_alloc,
)

# Process-wide singleton.
_ORCHESTRATOR: Optional[IntelligenceOrchestrator] = None


def get_intelligence() -> IntelligenceOrchestrator:
    """Return the process-wide :class:`IntelligenceOrchestrator` singleton."""
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = IntelligenceOrchestrator()
    return _ORCHESTRATOR


def reset_intelligence() -> None:
    """Drop the singleton (mainly for tests)."""
    global _ORCHESTRATOR
    _ORCHESTRATOR = None


__all__ = [
    "IntelligenceOrchestrator",
    "MiningIntelligenceResult",
    "ModuleRegistry",
    "get_intelligence",
    "reset_intelligence",
    "wire_intelligence_into_mining",
    "unwire_intelligence_from_mining",
    "run_intelligence_self_test",
    "PythiaLearning",
    "LearningResult",
    "LearnedPattern",
    "PythiaMemorySystem",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ArchivalMemory",
    "CognitiveScaffolding",
    "SocraticFeedbackLoop",
    "MetaCognitiveReflection",
    "AGIASIRequirements",
    "RequirementsReport",
    "SchoolVerdict",
    "PenroseOrchOR",
    "IntegratedInformation",
    "GlobalWorkspace",
    "FreeEnergyPrinciple",
    "AgenticController",
    "PolyhedralMapping",
    "SolverType",
    "LandscapeType",
    "LucasScaleProfile",
    "LucasScaleLevel",
    "build_lucas_scale_profile",
    "multiscale_coherence_probe",
    "LUCAS_SCALE_LADDER",
    "SCALE_ORDER",
    "SafetyController",
    "MiningState",
    "HashrateCapEnforcer",
    "ConsecutiveBlockGuard",
    "PredictiveSolver",
    "PredictionResult",
    "CounterfactualIntelligence",
    "IntelligenceModality",
    "Manifold11D",
    "project_to_11d",
    "HardwareProfile",
    "detect_hardware_profile",
    "get_hardware_profile",
    "reset_hardware_profile",
    "seed_pythia_knowledge",
    "KNOWLEDGE_FACTS",
    "seed_tool_knowledge",
    "get_tool_summary",
    "PythiaTool",
    "TOOLS",
    "seed_skill_knowledge",
    "get_skill_summary",
    "PythiaSkill",
    "discover_skills",
    "TOEBridge",
    "TOEStateTomography",
    "TOETrajectoryPrediction",
    "TOECausalAnalysis",
    "CausalLadderResult",
    "create_toe_bridge",
    "CausalGraph",
    "StructuralCausalModel",
    "infer_causal_graph",
    "do_operator",
    "counterfactual_query",
    "identify_backdoor",
    "identify_frontdoor",
    "SalamanderEngine",
    "HomeostasisMonitor",
    "HomeostasisReport",
    "SelfRepairEngine",
    "RepairProposal",
    "CircuitBreaker",
    "LucasIntelligenceScaler",
    "LucasScaleResult",
    "Complex",
    "ComplexMatrix",
    "QuantumState",
    "Observables",
    "quantum_fisher_information",
    "encode_data_to_state",
    "state_tomography",
    "path_integral_propagate",
    "trajectory_forecast",
    "causal_factor_ranking",
    "born_probabilities",
    "density_matrix_purity",
    "decoherence_measure",
    "model_agreement_from_ensemble",
    "project_to_32_face",
    "effective_subspace_dimension",
    # 11D Poincaré-Golden Substrate & Zeckendorf Arithmetic
    "PHI",
    "PHI_INVERSE",
    "METALLIC_MEANS",
    "PRIME_BUCKETS",
    "compute_poincare_norm_sq",
    "poincare_golden_distance",
    "fold_poincare_11d_vector",
    "unfold_poincare_11d_vector",
    "ZeckendorfCertificate",
    "compute_zeckendorf_certificate",
    "generate_zeckendorf_decoupling_mask",
    "resolve_zeckendorf_slot",
    "encode_zeckendorf",
    "beatty_partition",
    "cassini_unimodular_det",
    "get_metallic_mean",
    # Salamander Allocation Substrate
    "AllocationSlot",
    "SalamanderPoincareAllocationManager",
    "AllocationManager",
    # Autonomous capabilities (self-healing / self-optimising / mining)
    "SelfHealingLoop",
    "FaultRecord",
    "AutonomySupervisor",
    "CassiniCycleLedger",
    "KNOWN_FAULT_TYPES",
    "CuopMeter",
    "CuopReading",
    "CuopLearner",
    "SelfOptimisingLoop",
    "ValidityLearner",
    "CoolDownController",
    "telemetry_snapshot",
    "cassini_fingerprint",
    # Universal Passport Hard Gates
    "UniversalPassportToken",
    "DecisionGateViolationError",
    "verify_passport_hard_gate",
    # Backend Binding (substrate-agnostic dispatch)
    "BackendBinder",
    "BackendDetector",
    "BackendType",
    "BoundBackend",
    "GPUUnavailableError",
    "get_compute_backend",
    "reset_compute_backend",
    # Neural Plasticity
    "NeuralPlasticity",
    "PlasticSynapse",
    "PlasticityEvent",
    "PlasticUnifiedRuntime",
    "QuantumPlasticity",
    # Apple Silicon
    "AppleSiliconDetector",
    "AppleSiliconInfo",
    "AppleNeuralEngine",
    "AppleMetal",
    "AppleAccelerate",
    "AppleUnifiedMemory",
    "AppleSiliconRuntime",
    "ApplePlasticity",
    # Memory Substrate
    "LucasQuantumMemory",
    "UnlimitedQuantumStore",
    "PVsNPMemoryProof",
    "PVsNPGPU",
    "QuantumGPU",
    "PrimeMemory",
    "ExponentialPrimeStore",
    "QuantumPrimeMemory",
    # Consolidated AGI substrates (former core_engine)
    "AGICapability",
    "AGIDegradationMode",
    "AGIRequest",
    "AGIResponse",
    "AGITelemetry",
    "CanonicalAGISubstrate",
    "create_canonical_agi_substrate",
    "AGISubstrate",
    "IntelligenceLayer",
    "IntelligenceState",
    "NobelFieldsIntelligence",
    "MathematicalDomain",
    "MathematicalInsight",
    # Consciousness measurement
    "consciousness",
    "ConsciousnessEngine",
    "ConsciousnessLevel",
    "ConsciousnessStateVector",
    "QuantumConsciousnessSystem",
    "QuantumPattern",
    "EmergenceMetrics",
    "EmergenceSnapshot",
    "SchoolActivity",
    # Self-healing / self-optimising autonomy plane
    "self_healing",
    "AutopoieticMetaOptimizer",
    "CircuitState",
    "LedgerLoadError",
    "SalamanderFailureBus",
    "SalamanderHardwareSmoother",
    "SalamanderWiringInspector",
    "SalamanderZeroTrustGovernor",
    "SelfRepairCycleReport",
    "StartupSelfHealingState",
    "TuningRecommendation",
    "VeritasLedger",
    "get_startup_self_healing_state",
    "run_self_repair_cycle",
    "start_startup_self_healing",
    # ASI attribute framework subpackage
    "asi",
    # Aethel topological storage substrate + overhead accounting
    "AddressSpace",
    "AethelQueue",
    "CassiniLedger",
    "FibonacciAddress",
    "LedgerEntry",
    "PrimeStorageManifold",
    "UnifiedSubstrate",
    "OpCost",
    "OverheadMeter",
    "container_bytes",
    "measure_alloc",
]
