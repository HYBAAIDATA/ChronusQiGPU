"""Exact weighted evidence scores with dependence-group caps and conflict refusal.

Scores are policy assessments, NOT measured probabilities of truth. Repeated
self-reasoning cannot cross the independent-evidence ceiling.
"""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import ContractError, ratio, sha, text


@dataclass(frozen=True)
class VerificationMethod:
    id: str
    kind: str
    verifier: str
    operator: str
    training_process: str
    independence_group: str
    strength: Fraction
    independence: Fraction
    coverage: Fraction
    adversarial: bool
    passed: bool
    evidence_digest: str

    def __post_init__(self):
        for value in (
            self.id,
            self.kind,
            self.verifier,
            self.operator,
            self.training_process,
            self.independence_group,
        ):
            text(value)
        for value in (self.strength, self.independence, self.coverage):
            ratio(value)
        if type(self.adversarial) is not bool or type(self.passed) is not bool:
            raise ContractError("typed verification verdict required")
        sha(self.evidence_digest)


@dataclass(frozen=True)
class VerificationPolicy:
    pass_threshold: Fraction
    independence_floor: Fraction
    self_ceiling: Fraction

    def __post_init__(self):
        for value in self.__dict__.values():
            ratio(value)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    confidence: Fraction
    independent: bool
    conflict: bool
    methods: tuple[VerificationMethod, ...]
    residual_risks: tuple[str, ...]


def verification_confidence(methods, identity, policy):
    if (
        type(methods) is not tuple
        or len(methods) > 64
        or len({m.id for m in methods}) != len(methods)
    ):
        raise ContractError("bounded distinct verifier reports required")
    groups = {}
    independent = False
    for m in methods:
        is_independent = (
            m.verifier != identity.id
            and m.operator != identity.operator
            and m.training_process != identity.training_process
            and m.independence >= policy.independence_floor
        )
        independent |= is_independent
        weight = m.strength * (m.independence if is_independent else Fraction(0)) * m.coverage
        groups[m.independence_group] = max(groups.get(m.independence_group, Fraction(0)), weight)
    complement = Fraction(1)
    for weight in groups.values():
        complement *= 1 - weight
    score = 1 - complement
    if not independent:
        score = min(
            policy.self_ceiling,
            max((m.strength * m.coverage for m in methods), default=Fraction(0)),
        )
    return score, independent


def verify(identity, methods, policy, *, require_independence=False):
    score, independent = verification_confidence(methods, identity, policy)
    conflict = any(not m.passed for m in methods)
    passed = bool(methods) and not conflict and score >= policy.pass_threshold
    if require_independence and not independent:
        passed = False
    residual = () if passed else ("insufficient, conflicting or dependent evidence",)
    return VerificationResult(passed, score, independent, conflict, methods, residual)
