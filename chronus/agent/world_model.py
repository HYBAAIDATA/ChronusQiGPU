"""Facts retain provenance, expiry, contradictions and dependency state."""

from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
from ._contracts import ContractError, integer, ratio, sha, text

N_REF = 200
ADJ_ACC_FLOOR = Fraction(85, 100)
MAX_DIM_SHARE = Fraction(2, 5)


class FactState(Enum):
    ACTIVE = "active"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"
    UNVERIFIED = "unverified"
    CONTESTED = "contested"


@dataclass(frozen=True)
class Fact:
    id: str
    proposition: str
    value: str
    provenance: str
    confidence: Fraction
    observed_at: int
    valid_from: int
    expires_at: int | None
    contradictions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    sensitivity: str = "internal"
    state: FactState = FactState.UNVERIFIED

    def __post_init__(self):
        for value in (self.id, self.proposition, self.value, self.sensitivity):
            text(value)
        sha(self.provenance)
        ratio(self.confidence)
        integer(self.observed_at)
        integer(self.valid_from)
        if self.expires_at is not None:
            integer(self.expires_at, minimum=self.valid_from + 1)
        if type(self.state) is not FactState:
            raise ContractError("typed fact state required")


class WorldModel:
    def __init__(self, ledger):
        self._facts = {}
        self.ledger = ledger

    @property
    def facts(self):
        return tuple(self._facts.values())

    def add_fact(self, fact, *, now, verified=False):
        if not isinstance(fact, Fact) or fact.id in self._facts:
            raise ContractError("distinct typed fact required")
        conflicts = [
            f
            for f in self._facts.values()
            if f.proposition == fact.proposition
            and f.value != fact.value
            and f.state is FactState.ACTIVE
        ]
        if type(verified) is not bool:
            raise ContractError("host verification flag must be typed")
        state = FactState.ACTIVE if verified else FactState.UNVERIFIED
        if (
            fact.observed_at > now
            or fact.valid_from > now
            or (fact.expires_at is not None and now >= fact.expires_at)
        ):
            state = FactState.STALE
        if any(
            self._facts.get(d) is None or self._facts[d].state is not FactState.ACTIVE
            for d in fact.dependencies
        ):
            state = FactState.STALE
        if any(fact.confidence <= f.confidence for f in conflicts):
            state = FactState.CONTRADICTED
        fact = replace(fact, state=state, contradictions=tuple(f.id for f in conflicts))
        self.ledger.append("effect_confirmed", {"phase": "fact_added", "fact": fact}, now=now)
        for f in conflicts:
            self._facts[f.id] = replace(
                f, state=FactState.CONTESTED, contradictions=f.contradictions + (fact.id,)
            )
        if conflicts:
            fact = replace(fact, state=FactState.CONTESTED)
        self._facts[fact.id] = fact
        return fact

    def refresh_stale_facts(self, *, now):
        for _ in range(len(self._facts) + 1):
            changed = False
            for f in tuple(self._facts.values()):
                if f.state not in (FactState.ACTIVE, FactState.UNVERIFIED):
                    continue
                if (
                    now < f.valid_from
                    or (f.expires_at is not None and now >= f.expires_at)
                    or any(
                        self._facts.get(d) is None or self._facts[d].state is not FactState.ACTIVE
                        for d in f.dependencies
                    )
                ):
                    self.ledger.append(
                        "effect_confirmed", {"phase": "fact_stale", "id": f.id}, now=now
                    )
                    self._facts[f.id] = replace(f, state=FactState.STALE)
                    changed = True
            if not changed:
                break

    def resolve_fact_conflict(
        self,
        new_id,
        old_id,
        new_quality,
        old_quality,
        policy,
        *,
        now,
        calibration=None,
        verify_calibration=None
    ):
        new, old = self._facts[new_id], self._facts[old_id]
        if new.proposition != old.proposition or new.value == old.value:
            raise ContractError("no proposition conflict to adjudicate")
        verdict = adjudicate_contradiction(
            new_quality,
            old_quality,
            policy,
            calibration=calibration,
            verify_calibration=verify_calibration,
            now=now,
        )
        self.ledger.append(
            "fact_adjudicated",
            {
                "new": new_id,
                "old": old_id,
                "new_quality": new_quality,
                "old_quality": old_quality,
                "policy": policy,
                "calibration": calibration,
                "verdict": verdict,
            },
            now=now,
        )
        if verdict == "SUPERSEDE":
            self._facts[old_id] = replace(old, state=FactState.SUPERSEDED)
            remaining = [
                f
                for f in self._facts.values()
                if f.id not in (new_id, old_id)
                and f.proposition == new.proposition
                and f.value != new.value
                and f.state in (FactState.ACTIVE, FactState.CONTESTED)
            ]
            self._facts[new_id] = replace(
                new, state=FactState.CONTESTED if remaining else FactState.ACTIVE
            )
        else:
            self._facts[new_id] = replace(new, state=FactState.CONTESTED)
            self._facts[old_id] = replace(old, state=FactState.CONTESTED)
        return verdict

    def retract(self, fact_id, *, now):
        f = self._facts[fact_id]
        self.ledger.append("memory_lesson_retracted", {"fact": fact_id}, now=now)
        self._facts[fact_id] = replace(f, state=FactState.RETRACTED)
        self.refresh_stale_facts(now=now)


@dataclass(frozen=True)
class EvidenceQuality:
    source_groups: tuple[str, ...]
    provenance_strength: Fraction
    recency: Fraction
    directness: Fraction
    replication: Fraction
    domain_authority: Fraction
    consistency: Fraction
    adversarial_resistance: Fraction
    evidence: tuple[str, ...]

    def __post_init__(self):
        if type(self.source_groups) is not tuple or type(self.evidence) is not tuple:
            raise ContractError("immutable evidence chains required")
        for name in (
            "provenance_strength",
            "recency",
            "directness",
            "replication",
            "domain_authority",
            "consistency",
            "adversarial_resistance",
        ):
            ratio(getattr(self, name))
        for ref in self.evidence:
            sha(ref)


@dataclass(frozen=True)
class AdjudicationPolicy:
    weights: tuple[int, ...]
    supersession_margin: Fraction
    replication_threshold: Fraction
    minimum_groups: int

    def __post_init__(self):
        if type(self.weights) is not tuple or len(self.weights) != 7 or not sum(self.weights):
            raise ContractError("seven nonzero-total explicit quality weights required")
        for w in self.weights:
            integer(w)
        ratio(self.supersession_margin)
        ratio(self.replication_threshold)
        integer(self.minimum_groups, minimum=2)


def evidence_strength(q, policy):
    values = (
        q.provenance_strength,
        q.recency,
        q.directness,
        q.replication,
        q.domain_authority,
        q.consistency,
        q.adversarial_resistance,
    )
    return sum((w * v for w, v in zip(policy.weights, values)), Fraction(0)) / sum(policy.weights)


def adjudicate_contradiction(new, old, policy, *, calibration=None, verify_calibration=None, now=0):
    if calibration is not None and calibration.admitted(
        policy, now=now, verify_signature=verify_calibration
    ):
        stronger = (
            evidence_strength(new, policy)
            > evidence_strength(old, policy) + policy.supersession_margin
        )
    else:
        names = (
            "provenance_strength",
            "recency",
            "directness",
            "replication",
            "domain_authority",
            "consistency",
            "adversarial_resistance",
        )
        stronger = (
            all(getattr(new, n) >= getattr(old, n) for n in names)
            and new.recency > old.recency
            and new.directness > old.directness
        )
    independent = len(set(new.source_groups)) >= policy.minimum_groups
    replicated = new.replication >= policy.replication_threshold
    if stronger and independent and replicated and len(new.evidence) >= policy.minimum_groups:
        return "SUPERSEDE"
    if not independent or not replicated:
        return "DEFER_TO_EXPERIMENT"
    return "RETAIN_WITH_TENSION"


@dataclass(frozen=True)
class CalibrationLineage:
    corpus_size: int
    corpus_digest: str
    method: str
    weights_version: str
    accuracy: Fraction
    dimension_accuracy: tuple[Fraction, ...]
    weight_intervals: tuple[tuple[Fraction, Fraction], ...]
    qualified_at: int
    expires_at: int
    signature: str

    def body(self):
        from ._contracts import canonical

        return canonical({k: v for k, v in self.__dict__.items() if k != "signature"})

    def admitted(self, policy, *, now, verify_signature):
        from ._contracts import digest

        if (
            verify_signature is None
            or self.corpus_size < N_REF
            or self.accuracy < ADJ_ACC_FLOOR
            or len(self.dimension_accuracy) != 7
            or len(self.weight_intervals) != 7
            or not self.qualified_at <= now < self.expires_at
            or self.weights_version != digest(policy.weights)
            or Fraction(max(policy.weights), sum(policy.weights)) > MAX_DIM_SHARE
        ):
            return False
        sha(self.corpus_digest)
        for value in self.dimension_accuracy:
            ratio(value)
        for low, high in self.weight_intervals:
            ratio(low)
            ratio(high)
            if low > high:
                return False
        uniform_in_ci = all(low <= Fraction(1, 7) <= high for low, high in self.weight_intervals)
        if uniform_in_ci and len(set(policy.weights)) != 1:
            return False
        return verify_signature(self.body(), self.signature)
