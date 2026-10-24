"""Turing Universal Quantum Computer — consolidated exact-quantum substrate.

This package consolidates every PYTHIA/MLA1517 module that constitutes the
Turing virtual quantum computer: the canonical exact register, Q[sqrt(5)] /
Pisot algebra, exact tensor witnesses, Lucas/Pisot
Hendrix schedule, large-scale stabilizer execution, the production phi-machine
facade, bounded phi-VQC ranking and the exact backends behind the product boundary.

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
pisot / hendrix       Lucas/Pisot scale contracts + Hendrix schedule
quantum_cuda          iGPU / Turing exact-math accelerator facade

Carved out to their owners: the mining production plane and the capacity
surface (mining/), copies of live TOE, Intelligence and Mining modules, and
the tensor forks (now aliases of Kellogg).

Product boundary (v1.3):
backends              backend registry, capability envelopes, admission and
                      refusal, and the fail-closed QPU boundary
capabilities          published capability matrix + enforced claim audit
certificates          verifiable run witnesses
console               the operator console (`turing-vqc`)
"""

from __future__ import annotations

from . import turing_core  # noqa: F401
from . import (  # noqa: F401
    exact_field,
    exact_state_vector,
    exact_tensor,
    hendrix,
    pisot,
    quantum_tensor,
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

# Heavy and optional-dependency modules are lazy so a base import stays cheap.
_LAZY_MODULES = {
    "hilbert",
    "register_tensor",
    "quantum_cuda",
    "lucas",
    "quantum_algorithms",
    "grover_exact_scale",
    "stabilizer",
    "phi_quantum_machine",
    "phi_verification",
    "phi_vqc",
    "quantum_walk",
    "quantum_library",
    "annealing",
    "swarm",
    "variational",
    "july_compat",
    "phi_machine",
    "midas_vqc",
    "trotter_simulation",
    "golden_quantum",
    "unified_theory",
    "surface_code_exact",
    "canonical_serialization",
    "exact_field_registry",
    # product boundary (v1.3)
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
    "software_stack",
}

_LAZY_SYMBOLS = {
    # additive typed public API (canonical VQCPipeline remains unchanged)
    "QuantumPipeline": "public_api",
    "TuringPipeline": "public_api",
    "AdvancedQuantumPipeline": "public_api",
    "PipelineConfig": "config",
    "CircuitIR": "contracts",
    "ParameterSpec": "contracts",
    "ParameterBindings": "contracts",
    "FiniteAnsatz": "contracts",
    "PauliZ": "contracts",
    "OptimizationResult": "contracts",
    "JobStatus": "contracts",
    "Estimate": "contracts",
    "QuantumRegister": "hilbert",
    "GroverExact": "hilbert",
    "ExactComplex": "hilbert",
    "QSqrt": "hilbert",
    "QSqrt2": "hilbert",
    "qft": "hilbert",
    "QuantumTensor": "register_tensor",
    "QuantumTensorAudit": "register_tensor",
    "QuantumSimulator": "quantum_cuda",
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
    "QuantumLibrary": "quantum_library",
    "LibraryResult": "quantum_library",
    "ExactLaneError": "quantum_library",
    "ExactnessAuditError": "quantum_library",
    "ExactnessReport": "quantum_library",
    "audit_exactness": "quantum_library",
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
    "UnifiedTheoryFoundation": "unified_theory",
    "UNIFIED_THEORY": "unified_theory",
    "PauliCheck": "surface_code_exact",
    "PlanarSurfaceCodeAlgebra": "surface_code_exact",
    "SurfaceCodeAlgebraReport": "surface_code_exact",
    "SurfaceCodeConvention": "surface_code_exact",
    "verify_surface_code_algebra": "surface_code_exact",
    "CanonicalSerializationError": "canonical_serialization",
    "canonical_serialize": "canonical_serialization",
    "canonical_sha256": "canonical_serialization",
    "ExactFieldReport": "exact_field_registry",
    "QZeta8": "exact_field_registry",
    "ZETA_8": "exact_field_registry",
    "verify_q_zeta_8_registry": "exact_field_registry",
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
    "execute_certified": "backends",
    "CertifiedExecution": "backends",
    "capability_report": "capabilities",
    "capability_matrix": "capabilities",
    "audit_claims": "capabilities",
    "render_matrix": "capabilities",
    "RunWitness": "certificates",
    "issue_witness": "certificates",
    "verify_witness": "certificates",
    "VQCComputationCertificate": "certificates",
    "issue_computation_certificate": "certificates",
    "verify_computation_certificate": "certificates",
    "replay_computation_certificate": "certificates",
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
    # six-phase software stack
    "DEFAULT_BASIS_GATES": "software_stack",
    "CouplingMap": "software_stack",
    "RoutingResult": "software_stack",
    "TranspilationReport": "software_stack",
    "QECCycleReport": "software_stack",
    "HybridJobSpec": "software_stack",
    "HybridIterationReceipt": "software_stack",
    "HybridOrchestrationReport": "software_stack",
    "HybridWorkloadOrchestrator": "software_stack",
    "PulseInstruction": "software_stack",
    "PulseSchedule": "software_stack",
    "PulseCompiler": "software_stack",
    "SoftwareStackReport": "software_stack",
    "build_ansatz_program": "software_stack",
    "program_to_qasm": "software_stack",
    "program_from_qasm": "software_stack",
    "qasm_roundtrip_report": "software_stack",
    "decompose_to_basis": "software_stack",
    "route_program": "software_stack",
    "optimize_program": "software_stack",
    "transpile_program": "software_stack",
    "run_surface_code_qec_cycle": "software_stack",
    "run_hybrid_workload": "software_stack",
    "compile_pulse_schedule": "software_stack",
    "run_quantum_software_stack": "software_stack",
}

__version__ = "1.0.0"


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
