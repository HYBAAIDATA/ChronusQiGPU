"""TOE — the PYTHIA Theory-of-Everything engine package.

Canonical package layout (consolidated from Intelligence/toe_*.py, the
original toe.py monolith, and the substrate modules it runs on):

    toe.engine                      the original PredictiveEngine + extended
                                    algebraic-family substrate (Pisot spectrum)
    toe.bridge                      TOEBridge — state tomography, unitary
                                    trajectory, Pearl causal ladder
    toe.expansion                   TOEExpansionEngine — proof-carrying
                                    collapse envelope (operator compile +
                                    Zeckendorf certificate + Pisot/Lucas
                                    scale program)
    toe.system                      TOESystem — 12-theorem arbiter +
                                    provenance across the agentic workflow
    toe.operator_compilers          deterministic typed-operator compilation
                                    for arbitrary payloads
    toe.causal_ladder               Pearl ladder: association / do-operator /
                                    counterfactuals over the Kellogg tensor
    toe.manifold_bridge             Galois-persistent candidate store +
                                    O(1) lookup
    toe.poincare_golden_11d         11D Poincare-golden fold/unfold +
                                    Zeckendorf certificates
    toe.poincare_yangmills          finite 2I Laplacian gap joined to TOE;
                                    says which capabilities that opens
    toe.hardened_unified_substrate  identity alias of aethel.hardened_unified_substrate
                                    (Cassini verifier + Zeckendorf codec;
                                    canonical implementation lives in aethel)
    toe.strict_quantum              strict quantum work-window certificates
    toe.intelligences/              the five intelligences (causal,
                                    geometric, plastic, counterfactual,
                                    quantum)

The tensor substrate itself is the separate top-level package
``kellogg/`` — TOE consumes it but does not own it:

    kellogg.quantum_tensor          32-dim Hilbert substrate: Complex,
                                    ComplexMatrix, QuantumState, Observables,
                                    Born rule, QFI
    kellogg.exact_tensor            Clifford+T substrate over exact
                                    Q(zeta_8) fractions — zero float drift
    kellogg.exact_field             exact sqrt over F4 = Q(zeta_8),
                                    plane-checked value algebra
    kellogg.tensor_ml               exact-tensor ML family + joblib-shaped
                                    deterministic persistence

TOE provides observed context and search-order heuristics to the canonical
mining path (mla1517.mining.toe_adapter). It never substitutes SHA256d
consensus and never decides share validity.
"""

# Canonical version declaration for the toe package — the only literal in
# the package; toe/engine.py derives from this (see
# reports/version_consolidation.md).
__version__ = "3.5.0"

from .bridge import (
    CausalLadderResult,
    TOEBridge,
    TOECausalAnalysis,
    TOEStateTomography,
    TOETrajectoryPrediction,
    create_toe_bridge,
)
from .expansion import (
    TOEExpansionEngine,
    TOEExpansionPolicy,
    TOEExpansionResult,
)
from .operator_compilers import OperatorSpec, compile_operator
from .system import TOEProvenanceRecord, TOESystem
from .engine import (
    AlgebraicFormulations,
    ExtendedAlgebraicFamily,
    ManifoldEnhancedFormulations,
    PredictiveEngine,
    strict_quantum_work_certificate,
)

__all__ = [
    "__version__",
    "TOEBridge",
    "TOEStateTomography",
    "TOETrajectoryPrediction",
    "TOECausalAnalysis",
    "CausalLadderResult",
    "create_toe_bridge",
    "TOEExpansionEngine",
    "TOEExpansionPolicy",
    "TOEExpansionResult",
    "TOESystem",
    "TOEProvenanceRecord",
    "OperatorSpec",
    "compile_operator",
    "PredictiveEngine",
    "ExtendedAlgebraicFamily",
    "AlgebraicFormulations",
    "ManifoldEnhancedFormulations",
    "strict_quantum_work_certificate",
    "UnifiedAnalyticsPlatform",
]


def __getattr__(name: str):
    if name == "UnifiedAnalyticsPlatform":
        from .unified import UnifiedAnalyticsPlatform

        return UnifiedAnalyticsPlatform
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
