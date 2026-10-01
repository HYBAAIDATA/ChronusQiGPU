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
                                    counterfactuals over the Kellogg tensor;
                                    d-separation backdoor sets, adjusted
                                    effect estimation, exact Q(phi) path
    toe.explanation                 outcome-specific explanation by
                                    intervention (exact Shapley)
    toe.agreement                   agreement between distinct evaluators
    toe.policy                      action selection over evaluated futures
    toe.receipts                    hash-chained, replayable provenance
                                    receipts
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
    toe.intelligence_state          IntelligenceState — one observation
                                    bound to statistical/tensor/temporal/
                                    algebraic/geometric/topological/
                                    causal-graph views; digest-enforced
                                    identity, no silent divergence
    toe.representation              structural signature -> lens selection
                                    with explicit rejection reasons
    toe.causal_stack                causal capability stack: identifiability
                                    oracle (IDENTIFIED / PARTIALLY / NOT /
                                    UNAVAILABLE), bounded structure learning
                                    returning equivalence classes, multi-
                                    counterfactual world comparison, and
                                    multi-future evaluation with exact
                                    uncertainty propagation
    toe.uncertainty                 native uncertainty axes (aleatoric /
                                    model / structural / identifiability /
                                    missing evidence) + measured
                                    calibration
    toe.decision_explanation        computational + contrastive explanation
                                    and explanation/decision falsification
    toe.planning                    declared-operator action generation +
                                    bounded multi-step planning vs the
                                    one-step greedy baseline
    toe.memory                      one store, five namespaces; content-
                                    addressed recall, consolidation with
                                    source receipts, regime invalidation
    toe.world_model                 declared-structure world model with
                                    revision states, decision->outcome
                                    binding, online adaptation metrics
    toe.meta_reasoning              bounded meta-controller, value of
                                    information, compute-aware routing
    toe.precision                   adaptive precision selection +
                                    float-vs-exact consequence measurement
    toe.topology                    operational discrete topology:
                                    components, reachability, boundaries,
                                    articulation bottlenecks
    toe.arbitration                 disagreement between surfaces reported
                                    as DISAGREEMENT + resolved by declared
                                    authority/calibration, never averaged
    toe.generalization              DomainAdapter boundary + capability
                                    matrix + invariance + transfer probes
    toe.self_governance             adversarial battery, pre-release
                                    self-checks, measured promotion
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
mining path (chronus.mla1517.mining.toe_adapter). It never substitutes SHA256d
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
from .intelligence_state import (
    DivergenceError,
    IntelligenceState,
    LensView,
)
from .representation import (
    choose,
    select_views,
    structural_signature,
)
from .causal_stack import (
    IDENTIFIED,
    NOT_IDENTIFIED,
    PARTIALLY_IDENTIFIED,
    UNAVAILABLE,
    compare_worlds,
    discover_structures,
    evaluate_futures,
    identifiability,
)
from .uncertainty import (
    calibrate_effects,
    calibrate_futures,
    uncertainty_report,
)
from .decision_explanation import (
    explain_contrastive,
    explain_decision,
    falsify_decision,
    falsify_explanation,
)
from .planning import (
    OperatorSpec as PlanningOperatorSpec,
    compare_plan_vs_greedy,
    generate_actions,
    greedy,
    plan,
    scm_env,
)
from .policy import decide_multiobjective
from .memory import MemoryStore
from .world_model import (
    MODEL_CONTRADICTED,
    MODEL_DRIFT,
    MODEL_SUPPORTED,
    INSUFFICIENT_EVIDENCE,
    OnlineAdapter,
    WorldModel,
    bind_outcome,
)
from .meta_reasoning import (
    meta_decide,
    value_of_information,
    choose_path,
)
from .precision import (
    float_error_bound,
    measure_exactness,
    select_precision,
)
from .topology import StateTopology, reachability_task
from .arbitration import arbitrate
from .generalization import (
    DomainAdapter,
    capability_matrix,
    invariance_report,
    run_capability,
    transfer_probe,
)
from .self_governance import (
    adversarial_battery,
    promotion_decision,
    self_check,
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
    "IntelligenceState",
    "LensView",
    "DivergenceError",
    "choose",
    "select_views",
    "structural_signature",
    "identifiability",
    "discover_structures",
    "compare_worlds",
    "evaluate_futures",
    "uncertainty_report",
    "calibrate_effects",
    "calibrate_futures",
    "explain_decision",
    "explain_contrastive",
    "falsify_explanation",
    "falsify_decision",
    "PlanningOperatorSpec",
    "generate_actions",
    "scm_env",
    "plan",
    "greedy",
    "compare_plan_vs_greedy",
    "decide_multiobjective",
    "MemoryStore",
    "WorldModel",
    "OnlineAdapter",
    "bind_outcome",
    "MODEL_SUPPORTED",
    "MODEL_DRIFT",
    "MODEL_CONTRADICTED",
    "INSUFFICIENT_EVIDENCE",
    "meta_decide",
    "value_of_information",
    "choose_path",
    "float_error_bound",
    "select_precision",
    "measure_exactness",
    "StateTopology",
    "reachability_task",
    "arbitrate",
    "DomainAdapter",
    "capability_matrix",
    "invariance_report",
    "run_capability",
    "transfer_probe",
    "adversarial_battery",
    "self_check",
    "promotion_decision",
    "IDENTIFIED",
    "NOT_IDENTIFIED",
    "PARTIALLY_IDENTIFIED",
    "UNAVAILABLE",
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
