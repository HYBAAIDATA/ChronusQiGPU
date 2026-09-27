"""Turing Universal Quantum Computer — consolidated exact-quantum substrate.

This package consolidates every PYTHIA/MLA1517 module that constitutes the
Turing virtual quantum computer: the canonical 11-qubit exact register, the
Q[sqrt(5)] / Pisot algebraic substrate, the exact tensor witnesses, the
strict-quantum work certificates, the Lucas/Pisot Hendrix schedule, and the
four-layer Aethel -> Tensor -> TURING -> iGPU production execution plane.

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
quantum_walk          coined cycle walk (sparse-exact) + closed-form
                      continuous-time hypercube walk (exact at any n)
annealing             exact TFIM free-fermion spectrum, adiabatic gap,
                      Landau-Zener tunnelling (symbolic, any n)
swarm                 QuantumSwarm — agents sampling exact Born distributions
turing_core.ten_thousand  TenThousandQubitSystem — the universal engine
register_tensor       QuantumTensor — audited facade over QuantumRegister
exact_tensor          canonical Q(sqrt(2)) + i Q(sqrt(2)) exact state vector
exact_state_vector    MLA1517 exact state-vector algebra (predecessor surface)
quantum_tensor        first-principles tensor layer over C^N (H, U, M, x, C)
strict_quantum        strict Q(i) work-window certificates
pisot / hendrix       Lucas/Pisot scale contracts + Hendrix schedule
search                Grover-exact / Merkle / preimage search primitives
turing_adapter        Turing-derived deterministic lane/nonce ordering
quantum_cuda          iGPU / Turing exact-math accelerator facade

Production plane (11-qubit VQC pipeline):
backend_binding, hardened_unified_substrate, unified_punch, bitcoin_hasher,
hash_pipeline, manifold_bridge, intelligences, toe_system, four_layer_stack,
scaled_execution (LucasScaledAethelExecutionAdapter).
"""

from __future__ import annotations

from . import turing_core  # noqa: F401  — always available (stdlib only)
from . import (  # noqa: F401 — light stdlib-only surfaces
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
from .turing_core import (  # noqa: F401 — canonical TURING core surface
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
from .pisot import (  # noqa: F401 — VQC control-plane contracts
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
from .hendrix import HendrixIGPUSearch  # noqa: F401
from .strict_quantum import (  # noqa: F401
    QComplex,
    QMatrix,
    QState,
    certify_work_window,
    rational_rotation,
    state_from_bytes,
    verify_certificate,
)

# ---------------------------------------------------------------------------
# Lazy surface: heavier or optional-dependency modules are resolved on first
# attribute access so `import turing_universal_quantum_computer` stays fast
# and never fails on a missing optional extra (sympy / scipy / networkx).
# ---------------------------------------------------------------------------

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
    "quantum_walk",
    "annealing",
    "swarm",
}

_LAZY_SYMBOLS = {
    # hilbert (requires sympy)
    "QuantumRegister": "hilbert",
    "GroverExact": "hilbert",
    "ExactComplex": "hilbert",
    "QSqrt": "hilbert",
    "QSqrt2": "hilbert",
    "qft": "hilbert",
    # register_tensor (requires sympy + numpy)
    "QuantumTensor": "register_tensor",
    "QuantumTensorAudit": "register_tensor",
    # production plane
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
    # universal n-qubit engine (default 10_000 qubits)
    "TenThousandQubitSystem": "turing_core.ten_thousand",
    "EntanglementRegistration": "turing_core.ten_thousand",
    "DEFAULT_UNIVERSAL_QUBITS": "turing_core.ten_thousand",
    "zeckendorf_valid": "turing_core.ten_thousand",
    # exact large-scale backends
    "StabilizerState": "stabilizer",
    "StabilizerDomainError": "stabilizer",
    "CoinedCycleWalk": "quantum_walk",
    "HypercubeWalk": "quantum_walk",
    "TransverseFieldIsing": "annealing",
    "landau_zener": "annealing",
    "adiabatic_condition": "annealing",
    "QuantumSwarm": "swarm",
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
