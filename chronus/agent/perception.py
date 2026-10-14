"""Typed provenance-bearing observations; inferred states never become direct evidence."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from ._contracts import ContractError, integer, ratio, sha, text, digest


class ObservationChannel(Enum):
    DIRECT_API = "direct_api"
    SENSOR = "sensor"
    LOG = "log"
    FILE = "file"
    DATABASE = "database"
    HUMAN_REPORT = "human_report"
    WEB = "web"
    INFERRED = "inferred"


@dataclass(frozen=True)
class Observation:
    id: str
    entity: str
    state: str
    observed_at: int
    channel: ObservationChannel
    source: str
    noise: Fraction
    confidence: Fraction
    raw_evidence: str
    confounded: bool = False

    def __post_init__(self):
        for value in (self.id, self.entity, self.state, self.source):
            text(value)
        integer(self.observed_at)
        ratio(self.noise)
        ratio(self.confidence)
        sha(self.raw_evidence)
        if type(self.channel) is not ObservationChannel or type(self.confounded) is not bool:
            raise ContractError("typed observation channel/confounder required")

    @property
    def fingerprint(self):
        return digest(self)


def perceive(interface, ledger, *, now, max_age_ns, confidence_floor):
    observation = interface.observe()
    if not isinstance(observation, Observation):
        raise ContractError("typed observation required")
    integer(max_age_ns)
    ratio(confidence_floor)
    if (
        observation.observed_at > now
        or now - observation.observed_at > max_age_ns
        or observation.confidence < confidence_floor
    ):
        raise ContractError("stale/future/insufficient-confidence observation")
    ledger.append("effect_confirmed", {"phase": "perception", "observation": observation}, now=now)
    return observation


@dataclass(frozen=True)
class ConfirmedEffect:
    action: str
    judgement: str
    pre: str
    post: str
    intended_state: str
    observed_state: str


def confirm_action_effect(action, pre, post, intended_state):
    if pre.entity != post.entity or post.observed_at < pre.observed_at:
        raise ContractError("observation identity/time mismatch")
    if post.channel is ObservationChannel.INFERRED:
        judgement = "NOT_CONFIRMED"
    elif pre.confounded or post.confounded:
        judgement = "CONFOUNDED"
    elif post.state == pre.state:
        judgement = "NO_CHANGE"
    elif post.state == intended_state:
        judgement = "CONSISTENT_WITH_CAUSATION"
    else:
        judgement = "UNEXPECTED_EFFECT"
    return ConfirmedEffect(
        action, judgement, pre.fingerprint, post.fingerprint, intended_state, post.state
    )


@dataclass(frozen=True)
class CausalEvidence:
    interventional_refs: tuple[str, ...] = ()
    controlled_replication_refs: tuple[str, ...] = ()
    confounders: tuple[str, ...] = ()


def assess_causality(action, pre, post, intended_state, evidence):
    """Evidence classifications are host-attested, not inferred from a matching delta."""
    for ref in evidence.interventional_refs + evidence.controlled_replication_refs:
        sha(ref)
    result = confirm_action_effect(action, pre, post, intended_state)
    if result.judgement != "CONSISTENT_WITH_CAUSATION":
        return result
    from dataclasses import replace

    if evidence.confounders:
        return replace(result, judgement="CONFOUNDED")
    if evidence.interventional_refs:
        return replace(result, judgement="CONFIRMED")
    if len(set(evidence.controlled_replication_refs)) >= 2:
        return replace(result, judgement="SUPPORTED")
    return result
