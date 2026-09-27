"""Self-healing / self-optimising autonomous subsystem (Salamander stack).

Promoted from ``legacy/`` during the intelligence consolidation. This is
the repository-level autonomy plane: diagnose test failures, classify them,
propose and (under explicit approval) apply repairs, tune itself, and audit
its own wiring — with a tamper-evident ledger recording every action.

- :func:`run_self_repair_cycle` — full diagnose → classify → propose →
  (gated) apply → verify-or-revert cycle.
- :class:`AutopoieticMetaOptimizer` — self-optimising tuning loop over
  observed metrics.
- :class:`SalamanderZeroTrustGovernor` — circuit-broken governance gate.
- :func:`start_startup_self_healing` — managed startup diagnosis task.
- :class:`VeritasLedger` — append-only integrity ledger for repair actions.

Modules that depended on the absent ``python_backend`` tree (the legacy
evolution engine and homeostasis daemon) remain archived in ``legacy/``.
"""

from .meta_optimizer import (
    AutopoieticMetaOptimizer,
    MetaOptimizerError,
    SelfObservedMetrics,
    TuningRecommendation,
)
from .governor import CircuitState, SalamanderZeroTrustGovernor
from .salamander_failure_bus import FailureEvent, SalamanderFailureBus
from .salamander_wiring_inspector import (
    SalamanderWiringInspector,
    SubsystemNode,
    WiringAuditReport,
)
from .self_repair import (
    ApplyResult,
    ClassifiedFailure,
    DiagnosisRun,
    LLMRepairOutcome,
    PytestFailure,
    RepairProposal,
    SelfRepairCycleReport,
    apply_and_verify,
    check_flaky_by_rerun,
    classify_diagnosis_runs,
    classify_failure,
    create_proposal,
    parse_pytest_stdout,
    propose_llm_repair,
    propose_rule_based_repair,
    run_full_diagnosis,
    run_pytest_suite,
    run_self_repair_cycle,
)
from .smoother import SalamanderHardwareSmoother
from .startup_self_healing import (
    StartupSelfHealingState,
    get_startup_self_healing_state,
    start_startup_self_healing,
)
from .veritas_ledger import LedgerLoadError, VeritasLedger

__all__ = [
    "ApplyResult",
    "AutopoieticMetaOptimizer",
    "CircuitState",
    "ClassifiedFailure",
    "DiagnosisRun",
    "FailureEvent",
    "LLMRepairOutcome",
    "LedgerLoadError",
    "MetaOptimizerError",
    "PytestFailure",
    "RepairProposal",
    "SalamanderFailureBus",
    "SalamanderHardwareSmoother",
    "SalamanderWiringInspector",
    "SalamanderZeroTrustGovernor",
    "SelfObservedMetrics",
    "SelfRepairCycleReport",
    "StartupSelfHealingState",
    "SubsystemNode",
    "TuningRecommendation",
    "VeritasLedger",
    "WiringAuditReport",
    "apply_and_verify",
    "check_flaky_by_rerun",
    "classify_diagnosis_runs",
    "classify_failure",
    "create_proposal",
    "get_startup_self_healing_state",
    "parse_pytest_stdout",
    "propose_llm_repair",
    "propose_rule_based_repair",
    "run_full_diagnosis",
    "run_pytest_suite",
    "run_self_repair_cycle",
    "start_startup_self_healing",
]
