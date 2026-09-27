"""Nine-Agent Operating Model — the verification/governance pipeline.

Layered, deterministic, isolation-enforced:

- TRUTH agents (Auditor, MathVerifier, SecurityVerifier, QuantumChecker,
  PrecisionSentinel, PinVerifier) are read-only classifiers. They never
  patch, never approve, never merge.
- CHANGE agents (Remediator, TestEngineer) emit bounded change bundles
  only — draft intent, complexity-capped, never self-applied.
- CONTROL agents: Governance emits PASS / FAIL / NOT_PROVABLE with a
  reason; Provenance writes only ``docs/provenance/<sha>.json``.

The honesty pin is audited by PinVerifier: every ``theorem_proven`` key
in the tree must pin to ``False``. "Agent is hypothesis; CI and substrate
are evidence."
"""

from hyba.operating_model.roles import (
    AGENT,
    LAYERS,
    VOCAB,
    REMEDIATOR_MAX_BYTES,
    REMEDIATOR_MAX_CYCLOMATIC,
    REMEDIATOR_MAX_FANOUT,
    REMEDIATOR_MAX_FILES,
    PROVENANCE_DIR,
    TESTS_DIR,
    may_approve,
    may_merge,
    may_write,
    repo_root,
    suite_is_non_tautological,
)
from hyba.operating_model.substrate import freeze_substrate, substrate_frozen
from hyba.operating_model.lemma import (
    FORBIDDEN_CITATIONS,
    LEMMA,
    LEMMA_GOLDEN_STRIDE,
    LEMMA_PHI_RESONANCE,
    ScopeViolation,
    ast_scope_check,
    citation_check,
    claim_complexity,
    collect_ordering_signoff,
    collect_signoff,
    lemma_signed,
    ordering_lemmas_signed,
    require_lemma,
    require_ordering_lemmas,
    use_lemma,
    use_ordering_lemma,
    verify_golden_stride,
    verify_lemma,
    verify_resonance_ordering,
)
from hyba.operating_model.failure_modes import (
    FAILURE_MODES,
    write_failure_modes,
    failure_modes_documented,
)
from hyba.operating_model.pipeline import run_pipeline

__all__ = [
    "AGENT",
    "LAYERS",
    "VOCAB",
    "REMEDIATOR_MAX_BYTES",
    "REMEDIATOR_MAX_CYCLOMATIC",
    "REMEDIATOR_MAX_FANOUT",
    "REMEDIATOR_MAX_FILES",
    "PROVENANCE_DIR",
    "TESTS_DIR",
    "FAILURE_MODES",
    "may_approve",
    "may_merge",
    "may_write",
    "suite_is_non_tautological",
    "freeze_substrate",
    "substrate_frozen",
    "require_lemma",
    "lemma_signed",
    "LEMMA",
    "FORBIDDEN_CITATIONS",
    "ScopeViolation",
    "verify_lemma",
    "use_lemma",
    "claim_complexity",
    "citation_check",
    "ast_scope_check",
    "collect_signoff",
    "LEMMA_GOLDEN_STRIDE",
    "LEMMA_PHI_RESONANCE",
    "verify_golden_stride",
    "verify_resonance_ordering",
    "use_ordering_lemma",
    "collect_ordering_signoff",
    "require_ordering_lemmas",
    "ordering_lemmas_signed",
    "write_failure_modes",
    "failure_modes_documented",
    "run_pipeline",
]
