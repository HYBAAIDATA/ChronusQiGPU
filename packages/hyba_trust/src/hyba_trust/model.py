"""States, legal transitions, roles and the atom record.

An atom is one unit of derived knowledge (a fact, a summary). It is never
simply "written" or "not written": it carries a trust state, and every change of
state is appended to ``state_history`` and never overwritten.

Differences from the v5 pseudocode (each has a test):

* ``proposed -> probation`` and ``proposed -> demoted`` are legal. In v5 the only
  exits from ``proposed`` were ``quarantined`` and ``retracted``, so a review's
  APPROVE / REJECT could never be applied to a freshly proposed atom.
* ``probation -> disputed`` is legal. v5 checked ``no_dispute_raised`` during
  probation but gave a dispute nowhere to go except ``demoted``.
* ``retracted -> quarantined`` (un-retract) is legal only through
  ``TrustFabric.unretract``, which requires two distinct second-line actors.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class State(str, enum.Enum):
    PROPOSED = "proposed"
    QUARANTINED = "quarantined"
    PROBATION = "probation"
    CANONICAL = "canonical"
    DISPUTED = "disputed"
    DEMOTED = "demoted"
    RETRACTED = "retracted"


class Projection(str, enum.Enum):
    FULL = "full"
    DOWNWEIGHTED = "downweighted"
    LABELED_UNVERIFIED = "labeled_unverified"
    LABELED_CONTESTED = "labeled_contested"
    EXCLUDED = "excluded"


DAY = 86_400


@dataclass(frozen=True)
class StateSpec:
    authoritative: bool
    projection: Projection
    ttl_seconds: Optional[int] = None
    retained: bool = True
    tombstoned: bool = False


STATES: dict[State, StateSpec] = {
    State.PROPOSED: StateSpec(False, Projection.LABELED_UNVERIFIED),
    State.QUARANTINED: StateSpec(False, Projection.LABELED_UNVERIFIED, ttl_seconds=14 * DAY),
    State.PROBATION: StateSpec(True, Projection.DOWNWEIGHTED, ttl_seconds=30 * DAY),
    State.CANONICAL: StateSpec(True, Projection.FULL),
    State.DISPUTED: StateSpec(False, Projection.LABELED_CONTESTED),
    State.DEMOTED: StateSpec(False, Projection.EXCLUDED),
    State.RETRACTED: StateSpec(False, Projection.EXCLUDED, tombstoned=True),
}

LEGAL_TRANSITIONS: dict[State, frozenset[State]] = {
    State.PROPOSED: frozenset({State.QUARANTINED, State.PROBATION, State.DEMOTED, State.RETRACTED}),
    State.QUARANTINED: frozenset({State.PROBATION, State.DEMOTED, State.RETRACTED}),
    State.PROBATION: frozenset({State.CANONICAL, State.DISPUTED, State.DEMOTED}),
    State.CANONICAL: frozenset({State.DISPUTED, State.DEMOTED}),
    State.DISPUTED: frozenset({State.CANONICAL, State.DEMOTED, State.RETRACTED}),
    State.DEMOTED: frozenset({State.QUARANTINED, State.RETRACTED}),
    State.RETRACTED: frozenset({State.QUARANTINED}),
}

# Entering these states runs the demotion cascade before the call returns.
CASCADE_STATES = frozenset({State.DEMOTED, State.RETRACTED, State.DISPUTED})

PROJECTION_WEIGHT: dict[State, float] = {
    State.CANONICAL: 1.0,
    State.PROBATION: 0.7,
    State.DISPUTED: 0.4,
    State.QUARANTINED: 0.3,
    State.PROPOSED: 0.0,
    State.DEMOTED: 0.0,
    State.RETRACTED: 0.0,
}


class RiskTier(enum.IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    REGULATORY = 4


# Review SLA per tier, in seconds.
REVIEW_SLA: dict[RiskTier, int] = {
    RiskTier.LOW: 72 * 3600,
    RiskTier.MEDIUM: 24 * 3600,
    RiskTier.HIGH: 8 * 3600,
    RiskTier.REGULATORY: 4 * 3600,
}

# Share of automatically reviewed atoms that a human also samples.
HUMAN_SAMPLING: dict[RiskTier, float] = {RiskTier.LOW: 0.10, RiskTier.MEDIUM: 0.25}


class Role(str, enum.Enum):
    SYSTEM = "system"
    AUTO_REVIEWER = "auto_reviewer"
    REVIEWER = "reviewer"
    VERIFIER = "verifier"
    DATA_OWNER = "data_owner"
    USE_CASE_OWNER = "use_case_owner"
    INCIDENT_COMMANDER = "incident_commander"
    SECOND_LINE = "second_line"
    SIGNATORY = "signatory"


HUMAN_ROLES = frozenset(Role) - {Role.SYSTEM, Role.AUTO_REVIEWER}


@dataclass(frozen=True)
class Actor:
    id: str
    roles: frozenset[Role]

    @staticmethod
    def of(actor_id: str, *roles: Role) -> "Actor":
        return Actor(actor_id, frozenset(roles))

    def has(self, *roles: Role) -> bool:
        return bool(self.roles & set(roles))

    @property
    def is_human(self) -> bool:
        return bool(self.roles & HUMAN_ROLES)


SYSTEM = Actor.of("system", Role.SYSTEM)


@dataclass(frozen=True)
class HistoryEntry:
    from_state: Optional[State]
    to_state: State
    actor: str
    rationale: str
    ts: int
    approvers: tuple[str, ...] = ()
    seq: int = 0


@dataclass
class Atom:
    id: str
    content: str
    proposer: str
    generating_agent: str
    risk_tier: RiskTier
    kind: str = "fact"  # "fact" or "summary"
    key: str = ""  # what the atom is a claim about; same key + different content = conflict
    derived_from: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    provenance: str = ""
    confidence: float = 0.0
    state: State = State.PROPOSED
    state_history: list[HistoryEntry] = field(default_factory=list)
    entered_state_at: int = 0
    canonical_since: Optional[int] = None
    stale: bool = False
    stale_reason: str = ""
    version: int = 1
    amenders: set[str] = field(default_factory=set)
    pending_approvals: dict[str, Actor] = field(default_factory=dict)  # HIGH+: approvals awaiting a second
    appeal_count: int = 0
    appeal_final: bool = False
    review_due_at: Optional[int] = None
    disputes: int = 0
    incorrect_serves: int = 0

    @property
    def authors(self) -> set[str]:
        """Everyone who may not approve this atom: proposer, generator, amenders."""
        return {self.proposer, self.generating_agent} | self.amenders

    @property
    def authoritative(self) -> bool:
        return STATES[self.state].authoritative
