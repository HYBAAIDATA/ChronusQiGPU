"""Per-task expiring grants; next-level assurance, demotion and revocation."""

from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
from ._contracts import ContractError, integer, ratio
from .assurance import assurance_required


class TrustLevel(IntEnum):
    OBSERVE = 0
    ADVISE = 1
    ASSIST = 2
    DELEGATE = 3
    OWN = 4


@dataclass(frozen=True)
class ReliabilityThreshold:
    success_95: Fraction
    success_99: Fraction
    max_catastrophic: Fraction
    max_silent_failure: Fraction
    max_intervention: Fraction
    max_calibration_error: Fraction
    minimum_trials: int

    def __post_init__(self):
        for name in (
            "success_95",
            "success_99",
            "max_catastrophic",
            "max_silent_failure",
            "max_intervention",
            "max_calibration_error",
        ):
            ratio(getattr(self, name))
        integer(self.minimum_trials, minimum=1)


@dataclass(frozen=True)
class TrustDecision:
    from_level: TrustLevel
    to_level: TrustLevel
    task_key: str
    decision: str
    rationale: str
    evidence_digest: str
    decided_at: int
    expires_at: int


def trust_transition(
    identity, task, current, metrics, attestation, *, now, expires_at, thresholds, verifier_keys
):
    if type(current) is not TrustLevel or metrics.task_key != task.key:
        raise ContractError("typed task-bound current trust and metrics required")
    integer(now)
    integer(expires_at, minimum=now + 1)
    target = TrustLevel(min(int(current) + 1, int(TrustLevel.OWN)))
    required = thresholds.get(target)
    if required is None:
        raise ContractError("explicit promotion thresholds required; no defaults")
    decision, result, reason = "HOLD", current, "reliability thresholds not met"
    if (
        metrics.catastrophic_rate > required.max_catastrophic
        or metrics.silent_failure_rate > required.max_silent_failure
    ):
        decision, result, reason = (
            "SUSPEND",
            TrustLevel.OBSERVE,
            "catastrophic/silent failure bound exceeded",
        )
    elif (
        metrics.calibration_error > required.max_calibration_error and current > TrustLevel.OBSERVE
    ):
        decision, result, reason = "DEMOTE", TrustLevel(int(current) - 1), "calibration degraded"
    elif current > TrustLevel.OBSERVE and (
        metrics.n_trials < thresholds[current].minimum_trials
        or metrics.success_95 < thresholds[current].success_95
        or metrics.success_99 < thresholds[current].success_99
        or metrics.intervention_rate > thresholds[current].max_intervention
    ):
        decision, result, reason = (
            "DEMOTE",
            TrustLevel(int(current) - 1),
            "current-level reliability degraded",
        )
    elif current > TrustLevel.OBSERVE and (
        attestation is None
        or not attestation.admissible(identity, task, metrics, now, verifier_keys)
        or attestation.level < assurance_required(current, task)
    ):
        decision, result, reason = "SUSPEND", TrustLevel.OBSERVE, "current assurance not renewed"
    elif current == TrustLevel.OWN:
        reason = "already at maximum scoped authority"
    elif (
        attestation is None
        or not attestation.admissible(identity, task, metrics, now, verifier_keys)
        or attestation.level < assurance_required(target, task)
    ):
        reason = "insufficient independent target-level assurance"
    elif (
        metrics.n_trials >= required.minimum_trials
        and metrics.success_95 >= required.success_95
        and metrics.success_99 >= required.success_99
        and metrics.intervention_rate <= required.max_intervention
    ):
        decision, result, reason = (
            "PROMOTE",
            target,
            "measured criteria and independent assurance admitted",
        )
        expires_at = min(expires_at, attestation.expires_at)
    return TrustDecision(
        current, result, task.key, decision, reason, metrics.evidence_digest, now, expires_at
    )


class TrustProfile:
    def __init__(self):
        self._decisions = {}
        self._identity_binding = None

    def bind(self, identity):
        binding = (
            identity.id,
            identity.model_fingerprint,
            identity.tool_fingerprint,
            identity.policy_version,
        )
        if self._identity_binding is not None and self._identity_binding != binding:
            self._decisions.clear()
        self._identity_binding = binding

    def level(self, task, now):
        decision = self._decisions.get(task.key)
        return decision.to_level if decision and now < decision.expires_at else TrustLevel.OBSERVE

    def apply(
        self, decision, task, now, *, identity, metrics, attestation, thresholds, verifier_keys
    ):
        if decision.task_key != task.key or decision.from_level != self.level(task, now):
            raise ContractError("stale or cross-task trust decision")
        expected = trust_transition(
            identity,
            task,
            self.level(task, now),
            metrics,
            attestation,
            now=now,
            expires_at=decision.expires_at,
            thresholds=thresholds,
            verifier_keys=verifier_keys,
        )
        if decision != expected:
            raise ContractError("unissued or altered trust decision")
        self._decisions[task.key] = decision

    def revoke(self, task):
        self._decisions.pop(task.key, None)
