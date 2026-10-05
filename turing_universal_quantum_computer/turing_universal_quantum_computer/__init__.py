"""Turing Universal Quantum Computer — consolidated exact-quantum substrate.

This package consolidates every PYTHIA/MLA1517 module that constitutes the
Turing virtual quantum computer: the canonical exact register, Q[sqrt(5)] /
Pisot algebra, exact tensor witnesses, strict work certificates, Lucas/Pisot
Hendrix schedule, large-scale stabilizer execution, the production phi-machine
facade, bounded phi-VQC ranking and the four-layer production execution plane.

Layers
------
turing_core           exact Q[sqrt(5)] algebra, Zeckendorf, T_phi fold,
                      dual-overlay frame, complete nonce schedule, sha256d
                      engine, and (optional) the mathematical discovery engine
hilbert               QuantumRegister — canonical exact sparse state vector
                      over Q(i, sqrt(2)) + exact cyclotomics; n is unlimited,
                      support is bounded (fail-closed max_amplitudes)
stabilizer            StabilizerState — exact Clifford tableau; superposition,
                      entanglement and measurement at arbitrary n (incl. 10000)
phi_machine           HYBA 1,000-qubit Clifford execution profile on Turing,
                      QASM subset, exact T_phi checkpoint custody and bounded
                      algorithm capability metadata
midas_vqc             32-face variational nonce ranker + exact Clifford skeleton;
                      candidate ordering only, never mining consensus authority
quantum_walk          coined cycle walk (sparse-exact) + closed-form
                      continuous-time hypercube walk (exact at any n)
annealing             exact TFIM free-fermion spectrum, adiabatic gap,
                      Landau-Zener tunnelling (symbolic, any n)
swarm                 QuantumSwarm — agents sampling exact Born distributions
turing_core.ten_thousand  TenThousandQubitSystem — the universal engine
register_tensor       QuantumTensor — audited facade over QuantumRegister
exact_tensor          canonical Q(sqrt(2)) + i Q(sqrt(2)) exact state vector
exact_state_vector    MLA1517 exact state-vector algebra
quantum_tensor        first-principles tensor layer over C^N
strict_quantum        strict Q(i) work-window certificates
pisot / hendrix       Lucas/Pisot scale contracts + Hendrix schedule
search                Grover-exact / Merkle / preimage search primitives
turing_adapter        deterministic lane/nonce ordering
quantum_cuda          iGPU / Turing exact-math accelerator facade

Production plane:
backend_binding, hardened_unified_substrate, unified_punch, bitcoin_hasher,
hash_pipeline, manifold_bridge, intelligences, toe_system, four_layer_stack,
scaled_execution (LucasScaledAethelExecutionAdapter).

Product boundary (v1.2):
backends              backend registry, capability envelopes, admission and
                      refusal, and the fail-closed QPU boundary
capabilities          published capability matrix + enforced claim audit
certificates          verifiable run witnesses
console               the operator console (`turing-vqc`)
"""

from __future__ import annotations

from . import turing_core  # noqa: F401
from . import (  # noqa: F401
    duality,
    exact_field,
    exact_state_vector,
    exact_tensor,
    hendrix,
    kk_spectrum,
    pisot,
    quantum_tensor,
    strict_quantum,
)
from .turing_core import (  # noqa: F401
    FAMILY_COEFFS,
    PHI,
    PSI,
    HilbertOverlayProjector,
    MiningEngine,
    PythiaMiningEngine,
    TuringScheduleError,
    cassini_check,
    complete_nonce_schedule,
    doubling_check,
    extended_nonce_schedule,
    family_companion,
    family_root,
    fibonacci,
    generate_dual_overlay_frame,
    hash_meets_target,
    iter_nonce_schedule,
    lucas,
    nbits_to_target,
    padovan,
    pell,
    pell_lucas,
    perrin,
    run_self_verification,
    t_phi_fold,
    t_phi_unfold,
    target_to_difficulty,
    tribonacci,
    validate_schedule,
    zeckendorf_decode,
    zeckendorf_encode,
)
from .pisot import (  # noqa: F401
    DOMAIN_SCALE_INDEX,
    LUCAS_EXECUTION_SCALE_INDICES,
    SUPPORTED_SCALE_INDICES,
    VIRTUAL_QUANTUM_DIMENSION,
    VIRTUAL_QUANTUM_QUBITS,
    HendrixSchedule,
    HendrixStructuredSearch,
    HilbertCoveragePlan,
    LucasPisotScale,
    LucasScaleError,
    QuantumTensorManifest,
    plan_hilbert_coverage,
    require_lucas_execution_scale,
)
from .hendrix import HendrixChronusSearch  # noqa: F401
from .strict_quantum import (  # noqa: F401
    QComplex,
    QMatrix,
    QState,
    certify_work_window,
    rational_rotation,
    state_from_bytes,
    verify_certificate,
)

# Heavy and optional-dependency modules are lazy so a base import stays cheap.
_LAZY_MODULES = {
    "hilbert",
    "register_tensor",
    "search",
    "turing_adapter",
    "quantum_cuda",
    "backend_binding",
    "hardened_unified_substrate",
    "unified_punch",
    "bitcoin_hasher",
    "hash_pipeline",
    "manifold_bridge",
    "toe_system",
    "four_layer_stack",
    "scaled_execution",
    "rings",
    "extended_algebra",
    "intelligences",
    "lucas",
    "quantum_algorithms",
    "grover_exact_scale",
    "stabilizer",
    "phi_quantum_machine",
    "phi_verification",
    "phi_vqc",
    "quantum_walk",
    "annealing",
    "swarm",
    "variational",
    "july_compat",
    "phi_machine",
    "midas_vqc",
    "trotter_simulation",
    "golden_quantum",
    # product boundary (v1.2)
    "backends",
    "capabilities",
    "certificates",
    "console",
    # production path (v1.3)
    "taxonomy",
    "representation",
    "verify",
    "transform",
    "custody",
    "chronus_lane",
    "pipeline",
}

_LAZY_SYMBOLS = {
    "QuantumRegister": "hilbert",
    "GroverExact": "hilbert",
    "ExactComplex": "hilbert",
    "QSqrt": "hilbert",
    "QSqrt2": "hilbert",
    "qft": "hilbert",
    "QuantumTensor": "register_tensor",
    "QuantumTensorAudit": "register_tensor",
    "FourLayerMiningStack": "four_layer_stack",
    "TuringLayer": "four_layer_stack",
    "NearStateIGpu": "four_layer_stack",
    "AethelStore": "four_layer_stack",
    "TensorFoldEngine": "four_layer_stack",
    "LucasScaledAethelExecutionAdapter": "scaled_execution",
    "ScaledExecutionResult": "scaled_execution",
    "TOESystem": "toe_system",
    "TOEProvenanceRecord": "toe_system",
    "TuringMiningSubstrate": "turing_adapter",
    "TuringCoreUnavailable": "turing_adapter",
    "HashPipeline": "hash_pipeline",
    "UnifiedPunchHost": "unified_punch",
    "BitcoinHasher": "bitcoin_hasher",
    "ManifoldBridge": "manifold_bridge",
    "QuantumSimulator": "quantum_cuda",
    "ExtendedAlgebra": "extended_algebra",
    "GroverSearch": "quantum_algorithms",
    "run_folded": "grover_exact_scale",
    "TenThousandQubitSystem": "turing_core.ten_thousand",
    "EntanglementRegistration": "turing_core.ten_thousand",
    "DEFAULT_UNIVERSAL_QUBITS": "turing_core.ten_thousand",
    "zeckendorf_valid": "turing_core.ten_thousand",
    "StabilizerState": "stabilizer",
    "StabilizerDomainError": "stabilizer",
    "CoinedCycleWalk": "quantum_walk",
    "HypercubeWalk": "quantum_walk",
    "TransverseFieldIsing": "annealing",
    "landau_zener": "annealing",
    "adiabatic_condition": "annealing",
    "QuantumSwarm": "swarm",
    "AlgorithmResult": "july_compat",
    "CompositionStrategy": "july_compat",
    "EnhancedGroverAlgorithm": "july_compat",
    "EnhancedQuantumFourierTransform": "july_compat",
    "OptimizerStage": "july_compat",
    "QuantumAccelerationEngine": "july_compat",
    "UnsupportedAlgorithmError": "july_compat",
    "coordinate_descent_stage": "july_compat",
    "grid_search_stage": "july_compat",
    "redirect_historical_surface": "july_compat",
    "run_all_verifications": "july_compat",
    # recovered HYBA 1,000-qubit machine surface
    "PhiQuantumCircuit": "phi_machine",
    "PhiQuantumMachine1000": "phi_machine",
    "PhiCheckpoint": "phi_machine",
    "run_1000_qubit_verification": "phi_machine",
    "seeded_clifford_digest": "phi_machine",
    "state_digest": "phi_machine",
    # recovered MIDAS/VQC surface
    "MidasPhiVQCRanker": "midas_vqc",
    "VQCConfig": "midas_vqc",
    "TrotterHamiltonianSimulator": "trotter_simulation",
    "GoldenQuantumCore": "golden_quantum",
    "GoldenConstants": "golden_quantum",
    "GOLDEN_CONSTANTS": "golden_quantum",
    "EvidenceLayer": "golden_quantum",
    "UniversalConstantInterface": "golden_quantum",
    "PrimeGapAddressSpace": "golden_quantum",
    "MandelbrotResonanceEngine": "golden_quantum",
    "SearchAttestation": "golden_quantum",
    # product boundary (v1.2)
    "Program": "backends",
    "Operation": "backends",
    "ExecutionResult": "backends",
    "ExecutionClass": "backends",
    "TruthClass": "backends",
    "Capability": "backends",
    "Admission": "backends",
    "ExactStatevector": "backends",
    "ExactFieldBackend": "backends",
    "StabilizerBackend": "backends",
    "SparseExactBackend": "backends",
    "ClosedFormBackend": "backends",
    "QPUBackend": "backends",
    "QPUUnavailableError": "backends",
    "QPUClaimError": "backends",
    "QPUJob": "backends",
    "assert_measured_qpu": "backends",
    "backend_matrix": "backends",
    "select_backend": "backends",
    "execute": "backends",
    "capability_report": "capabilities",
    "capability_matrix": "capabilities",
    "audit_claims": "capabilities",
    "render_matrix": "capabilities",
    "RunWitness": "certificates",
    "issue_witness": "certificates",
    "verify_witness": "certificates",
    "QuantumConsole": "console",
    # production path (v1.3)
    "ExecutionKind": "taxonomy",
    "EvidenceState": "taxonomy",
    "ExecutionKindReport": "taxonomy",
    "classify_execution": "taxonomy",
    "evidence_states": "taxonomy",
    "REPRESENTATIONS": "representation",
    "DOMINANCE": "representation",
    "RepresentationChoice": "representation",
    "RepresentationPlanner": "representation",
    "plan_representation": "representation",
    "UnitarityReport": "verify",
    "verify_program_unitarity": "verify",
    "program_unitary_columns": "verify",
    "OvidTransform": "transform",
    "TransformRecord": "transform",
    "open_transform": "transform",
    "ovid_available": "transform",
    "TuringCustody": "custody",
    "CustodyReceipt": "custody",
    "ReplayReport": "custody",
    "open_custody": "custody",
    "theseus_available": "custody",
    "ChronusLaneStatus": "chronus_lane",
    "probe_chronus_lane": "chronus_lane",
    "chronus_available": "chronus_lane",
    "VQCRequest": "pipeline",
    "PipelineReport": "pipeline",
    "StageEvidence": "pipeline",
    "VQCPipeline": "pipeline",
    "run_pipeline": "pipeline",
}

__version__ = "1.2.0"


def __getattr__(name: str):
    import importlib

    if name in _LAZY_MODULES:
        return importlib.import_module(f".{name}", __name__)
    module_name = _LAZY_SYMBOLS.get(name)
    if module_name is not None:
        module = importlib.import_module(f".{module_name}", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY_MODULES) | set(_LAZY_SYMBOLS))
