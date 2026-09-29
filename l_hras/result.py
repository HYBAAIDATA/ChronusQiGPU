"""L-HRAS Result monad and error taxonomy (Parts I, XIII).

The blueprint's ``?`` operator is honoured by convention: every operator
returns ``Result[T]``; callers propagate ``Err`` values unchanged. An
``Err`` always carries an :class:`LHRASError` whose ``code`` is a name
from the declared taxonomy — never a bare string, never an exception
that escaped. Failure is a value, and where the blueprint intends it,
it fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Error taxonomy — Part XIII. These names are the contract; callers and tests
# match on ``code``.
# ---------------------------------------------------------------------------

# Preconditions / configuration
CONFIG_INCOMPLETE = "config_incomplete"
PNP_RATIO_OUT_OF_RANGE = "pnp_ratio_out_of_range"
VISCOSITY_NONPOSITIVE = "viscosity_nonpositive"
FOLD_TOLERANCE_NONPOSITIVE = "fold_tolerance_nonpositive"
MAX_CF_NONPOSITIVE = "max_cf_nonpositive"
PURITY_THRESHOLD_INVALID = "purity_threshold_invalid"
ENTROPY_THRESHOLD_INVALID = "entropy_threshold_invalid"
THRESHOLD_PROVENANCE_MISSING = "threshold_provenance_missing"

THREAT_MODEL_MISSING = "threat_model_missing"
THREAT_MODEL_MALFORMED = "threat_model_malformed"
TRUST_ROOT_MISSING = "trust_root_missing"
SWARM_TOO_SMALL = "swarm_too_small"
POLICY_BUNDLE_INVALID = "policy_bundle_invalid"

NOT_STANDING = "not_standing"
POLICY_VIOLATION = "policy_violation"
FORGERY_DETECTED = "forgery_detected"

ENTANGLEMENT_BREAK = "entanglement_break"
MULTIPLY_FAILED = "multiply_failed"
SWARM_QUORUM_FAILED = "swarm_quorum_failed"
CONSENSUS_FAILED = "consensus_failed"
WILLOW_FAILED = "willow_failed"

PREDICTION_FAILED = "prediction_failed"
COUNTERFACTUAL_FAILED = "counterfactual_failed"
CAUSAL_ASSOCIATION_FAILED = "causal_association_failed"
CAUSAL_INTERVENTION_FAILED = "causal_intervention_failed"
CAUSAL_COUNTERFACTUAL_FAILED = "causal_counterfactual_failed"

TOPOLOGICAL_ANALYSIS_FAILED = "topological_analysis_failed"
GEOMETRIC_ANALYSIS_FAILED = "geometric_analysis_failed"
QUANTUM_FOLD_FAILED = "quantum_fold_failed"

POINCARE_ISOLATION_FAILED = "poincare_isolation_failed"
PNP_RATIO_VIOLATED = "pnp_ratio_violated"
YM_FIELD_BROKEN = "ym_field_broken"
RIEMANN_BELOW_CRITICAL_LINE = "riemann_below_critical_line"
BSD_RANK_EXCEEDED = "bsd_rank_exceeded"
HODGE_UNKNOWN_CLASS = "hodge_unknown_class"
NS_BLOW_UP = "ns_blow_up"

FOLD_NOT_EXACT = "fold_not_exact"
UNFOLD_FAILED = "unfold_failed"
CERTIFICATE_REPLAY_FAILED = "certificate_replay_failed"

ATTESTATION_FAILURE = "attestation_failure"
AETHEL_WRITE_FAILURE = "aethel_write_failure"
CODE_INTEGRITY_FAILURE = "code_integrity_failure"

BREAK_GLASS_DENIED = "break_glass_denied"
SSO_AUTH_FAILED = "sso_auth_failed"

SECURITY_VIOLATION = "security_violation"
PRIVACY_VIOLATION = "privacy_violation"
UNKNOWN = "unknown"

TAXONOMY = frozenset(
    name
    for name in (
        CONFIG_INCOMPLETE,
        PNP_RATIO_OUT_OF_RANGE,
        VISCOSITY_NONPOSITIVE,
        FOLD_TOLERANCE_NONPOSITIVE,
        MAX_CF_NONPOSITIVE,
        PURITY_THRESHOLD_INVALID,
        ENTROPY_THRESHOLD_INVALID,
        THRESHOLD_PROVENANCE_MISSING,
        THREAT_MODEL_MISSING,
        THREAT_MODEL_MALFORMED,
        TRUST_ROOT_MISSING,
        SWARM_TOO_SMALL,
        POLICY_BUNDLE_INVALID,
        NOT_STANDING,
        POLICY_VIOLATION,
        FORGERY_DETECTED,
        ENTANGLEMENT_BREAK,
        MULTIPLY_FAILED,
        SWARM_QUORUM_FAILED,
        CONSENSUS_FAILED,
        WILLOW_FAILED,
        PREDICTION_FAILED,
        COUNTERFACTUAL_FAILED,
        CAUSAL_ASSOCIATION_FAILED,
        CAUSAL_INTERVENTION_FAILED,
        CAUSAL_COUNTERFACTUAL_FAILED,
        TOPOLOGICAL_ANALYSIS_FAILED,
        GEOMETRIC_ANALYSIS_FAILED,
        QUANTUM_FOLD_FAILED,
        POINCARE_ISOLATION_FAILED,
        PNP_RATIO_VIOLATED,
        YM_FIELD_BROKEN,
        RIEMANN_BELOW_CRITICAL_LINE,
        BSD_RANK_EXCEEDED,
        HODGE_UNKNOWN_CLASS,
        NS_BLOW_UP,
        FOLD_NOT_EXACT,
        UNFOLD_FAILED,
        CERTIFICATE_REPLAY_FAILED,
        ATTESTATION_FAILURE,
        AETHEL_WRITE_FAILURE,
        CODE_INTEGRITY_FAILURE,
        BREAK_GLASS_DENIED,
        SSO_AUTH_FAILED,
        SECURITY_VIOLATION,
        PRIVACY_VIOLATION,
        UNKNOWN,
    )
)


class LHRASError(Exception):
    """A taxonomy-named failure. ``code`` is always in :data:`TAXONOMY`."""

    def __init__(self, code: str, detail: dict[str, Any] | None = None):
        if code not in TAXONOMY:
            raise ValueError(f"undeclared error code: {code}")
        self.code = code
        self.detail = dict(detail or {})
        super().__init__(f"{code}: {self.detail}" if self.detail else code)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": dict(self.detail)}


class Result(Generic[T]):
    """Base of :class:`Ok` / :class:`Err`. Falsy when it is an error."""

    __slots__ = ()

    @property
    def is_ok(self) -> bool:
        return isinstance(self, Ok)

    @property
    def is_err(self) -> bool:
        return isinstance(self, Err)

    def __bool__(self) -> bool:
        return self.is_ok

    def unwrap(self) -> T:
        raise NotImplementedError

    def unwrap_or(self, default: T) -> T:
        return self.unwrap() if self.is_ok else default


@dataclass(frozen=True)
class Ok(Result[T]):
    value: T

    def unwrap(self) -> T:
        return self.value


@dataclass(frozen=True)
class Err(Result[T]):
    error: LHRASError = field()

    def unwrap(self) -> T:
        raise self.error


def error(code: str, **detail: Any) -> Err:
    """Build an ``Err`` carrying a taxonomy-named failure."""
    return Err(LHRASError(code, detail))


def propagate(result: Result) -> LHRASError | None:
    """Return the inner error for ``?``-style early returns, else None."""
    return result.error if isinstance(result, Err) else None
