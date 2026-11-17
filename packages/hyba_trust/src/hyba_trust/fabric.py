"""TrustFabric: atom store, transitions, demotion cascade and promotion authority.

One object owns every atom, the lineage index, the review queues, the use-case
registry and the promotion ledger, so a transition and its cascade happen in one
call: a demotion returns only after the cascade has run (stale marks, dependent
atoms disputed, re-validation queued, notifications in the outbox, manifest and
ledger entry written).

Notification *delivery* is deliberately outside that guarantee. The cascade
writes one notification per affected use case to ``outbox`` before it returns;
delivery is retried by the caller (``deliver_notifications``) and failures stay
visible as undelivered entries. A mail outage therefore cannot block a demotion,
and cannot lose the notice either.

Fixes over the v5 pseudocode, each covered by a test:

1. Dual control is checked before the transition, not after it.
2. A reviewer who amends an atom becomes one of its authors and cannot approve it.
3. The cascade moves both ``canonical`` and ``probation`` descendants to
   ``disputed`` (v5 left probation descendants to auto-promote).
4. ``probation -> disputed`` exists (see model.py).
5. The cascade walks lineage once with a visited set and writes one manifest per
   root; it never re-enters itself.
6. Un-retract needs two distinct second-line actors (``unretract``).
7. Reviews can act on ``proposed`` atoms (see model.py).
8. Probation is decided only once its TTL has elapsed; before that, nothing.
9. Appeals are capped at two; the second-line decision on the second appeal is final.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .ledger import PromotionLedger
from .model import (
    CASCADE_STATES,
    DAY,
    HUMAN_SAMPLING,
    LEGAL_TRANSITIONS,
    REVIEW_SLA,
    STATES,
    SYSTEM,
    Actor,
    Atom,
    HistoryEntry,
    RiskTier,
    Role,
    State,
)

RETRO_REVIEW_WINDOW = 2 * DAY
LONG_CANONICAL = 30 * DAY
MAX_APPEALS = 2


class TrustError(Exception):
    """Base class for refused operations."""


class IllegalTransition(TrustError):
    pass


class NotAuthorized(TrustError):
    pass


class SelfApproval(NotAuthorized):
    pass


class StaleReviewPacket(TrustError):
    """The reviewer did not see the atom as it is now."""


class AppealRefused(TrustError):
    pass


_ENTRY_ROLES: dict[State, frozenset[Role]] = {
    State.QUARANTINED: frozenset({Role.SYSTEM, Role.DATA_OWNER, Role.SECOND_LINE}),
    State.PROBATION: frozenset({Role.AUTO_REVIEWER, Role.REVIEWER, Role.VERIFIER, Role.SECOND_LINE}),
    State.CANONICAL: frozenset({Role.SYSTEM, Role.REVIEWER, Role.VERIFIER, Role.SECOND_LINE}),
    State.DISPUTED: frozenset({Role.SYSTEM, Role.REVIEWER, Role.VERIFIER, Role.DATA_OWNER,
                               Role.USE_CASE_OWNER, Role.INCIDENT_COMMANDER, Role.SECOND_LINE}),
    State.DEMOTED: frozenset({Role.SYSTEM, Role.AUTO_REVIEWER, Role.REVIEWER, Role.VERIFIER, Role.DATA_OWNER,
                              Role.USE_CASE_OWNER, Role.INCIDENT_COMMANDER, Role.SECOND_LINE}),
    State.RETRACTED: frozenset({Role.DATA_OWNER, Role.INCIDENT_COMMANDER, Role.SECOND_LINE}),
}

# The only moves the system actor may make on its own.
_SYSTEM_MOVES = frozenset({
    (State.PROPOSED, State.QUARANTINED),      # degraded mode: overdue review
    (State.PROBATION, State.CANONICAL),       # probation complete
    (State.PROBATION, State.DEMOTED),         # probation failed
    (State.QUARANTINED, State.DEMOTED),       # quarantine expired unreviewed
    (State.CANONICAL, State.DISPUTED),        # cascade
    (State.PROBATION, State.DISPUTED),        # cascade
})

_APPROVAL_ROLES = (Role.REVIEWER, Role.VERIFIER, Role.SECOND_LINE)

_RETRO_ROLES = (Role.REVIEWER, Role.VERIFIER, Role.DATA_OWNER, Role.INCIDENT_COMMANDER, Role.USE_CASE_OWNER)


def _fraction(key: str) -> float:
    """Deterministic value in [0, 1) for reproducible sampling."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) / 2**32


@dataclass
class UseCase:
    id: str
    owner: str
    depends_on: frozenset[str]
    in_production: bool = False


@dataclass
class Revalidation:
    use_case_id: str
    root_atom: str
    opened_at: int
    retro_review_due: int
    resolved_how: Optional[str] = None
    resolved_by: Optional[str] = None

    @property
    def open(self) -> bool:
        return self.resolved_how is None


@dataclass
class Notification:
    to: str
    use_case_id: str
    report: dict
    delivered: bool = False
    attempts: int = 0
    last_error: Optional[str] = None


@dataclass(frozen=True)
class CascadeManifest:
    root: str
    cause: State
    descendants: tuple[str, ...]
    summaries: tuple[str, ...]
    disputed: tuple[str, ...]
    use_cases: tuple[str, ...]
    production_use_cases: tuple[str, ...]
    started_at: int
    finished_at: int


@dataclass(frozen=True)
class ReviewPacket:
    """What a reviewer must have seen. Bound to the atom's current version."""
    atom_id: str
    version: int
    content: str
    evidence: tuple[str, ...]
    provenance: str
    blast_radius: tuple[str, ...]
    use_cases: tuple[str, ...]
    conflicts: tuple[str, ...]
    digest: str


@dataclass
class ReviewTask:
    atom_id: str
    queue: str
    due_at: int
    human_required: bool
    dual_control: bool
    signatory_required: bool
    second_line_required: bool = False
    appeal_evidence: tuple[str, ...] = ()
    opened_at: int = 0
    closed_at: Optional[int] = None


@dataclass
class Output:
    id: str
    atom_ids: frozenset[str]
    ts: int


@dataclass
class Citation:
    atom_id: str
    as_fact: bool
    state: State


class TrustFabric:
    def __init__(self, clock: Callable[[], int] = lambda: int(time.time()),
                 retro_sample_rate: float = 0.2) -> None:
        self.clock = clock
        self.retro_sample_rate = retro_sample_rate
        self.atoms: dict[str, Atom] = {}
        self.children: dict[str, set[str]] = {}
        self.use_cases: dict[str, UseCase] = {}
        self.revalidations: list[Revalidation] = []
        self.outbox: list[Notification] = []
        self.cascades: list[CascadeManifest] = []
        self.reviews: dict[str, ReviewTask] = {}
        self.outputs: list[Output] = []
        self.recheck_queue: list[tuple[str, str]] = []  # (output id, demoted atom id)
        self.citations: list[Citation] = []
        self.ledger = PromotionLedger()
        self._seq = 0

    # ------------------------------------------------------------- writing

    def _require(self, atom_id: str) -> Atom:
        try:
            return self.atoms[atom_id]
        except KeyError:
            raise TrustError(f"unknown atom {atom_id!r}") from None

    def _index_lineage(self, atom: Atom) -> None:
        for parent in atom.derived_from:
            self._require(parent)
            self.children.setdefault(parent, set()).add(atom.id)

    def propose(self, atom: Atom, session: str = "") -> ReviewTask:
        """Write an atom as ``proposed`` (working tier) and route it to review by risk."""
        if atom.id in self.atoms:
            raise TrustError(f"atom {atom.id!r} already exists")
        if atom.kind == "summary" and not atom.derived_from:
            raise TrustError("a summary must record derived_from, or the cascade cannot reach it")
        for parent in atom.derived_from:
            self._require(parent)
        now = self.clock()
        atom.state = State.PROPOSED
        atom.entered_state_at = now
        self._seq += 1
        atom.state_history.append(HistoryEntry(None, State.PROPOSED, atom.proposer, f"proposed (session {session})",
                                               now, seq=self._seq))
        self.atoms[atom.id] = atom
        self._index_lineage(atom)
        task = self._route(atom, now)
        self.ledger.append("proposed", atom=atom.id, tier=atom.risk_tier.name, proposer=atom.proposer,
                           generating_agent=atom.generating_agent, queue=task.queue, due_at=task.due_at, ts=now)
        return task

    def _route(self, atom: Atom, now: int, *, second_line: bool = False,
               appeal_evidence: tuple[str, ...] = ()) -> ReviewTask:
        tier = atom.risk_tier
        if second_line:
            queue = "second_line"
        elif tier >= RiskTier.HIGH:
            queue = tier.name.lower()
        else:
            queue = "auto_review"
        sampled = tier in HUMAN_SAMPLING and _fraction(f"{atom.id}:{atom.version}") < HUMAN_SAMPLING[tier]
        task = ReviewTask(
            atom_id=atom.id,
            queue=queue,
            due_at=now + REVIEW_SLA[tier],
            human_required=second_line or tier >= RiskTier.HIGH or sampled,
            dual_control=tier >= RiskTier.HIGH,
            signatory_required=tier == RiskTier.REGULATORY,
            second_line_required=second_line,
            appeal_evidence=appeal_evidence,
            opened_at=now,
        )
        self.reviews[atom.id] = task
        return task

    # --------------------------------------------------------- transitions

    def _authorize(self, actor: Actor, atom: Atom, frm: State, to: State) -> None:
        if not actor.has(*_ENTRY_ROLES.get(to, ())):
            raise NotAuthorized(f"{actor.id} may not move atoms to {to.value}")
        if actor.has(Role.SYSTEM) and (frm, to) not in _SYSTEM_MOVES:
            raise NotAuthorized(f"system may not move {frm.value} -> {to.value}")
        if actor.has(Role.AUTO_REVIEWER) and not actor.is_human and atom.risk_tier >= RiskTier.HIGH:
            raise NotAuthorized("automatic review cannot decide HIGH or REGULATORY atoms")
        if to is State.CANONICAL and actor.is_human and frm is not State.DISPUTED:
            raise NotAuthorized("people reach canonical only by resolving a dispute; otherwise probation decides")
        if frm is State.RETRACTED and not actor.has(Role.SECOND_LINE):
            raise NotAuthorized("only second line may un-retract")

    def _check_approvers(self, atom: Atom, approvers: dict[str, Actor]) -> None:
        clash = set(approvers) & atom.authors
        if clash:
            raise SelfApproval(f"{', '.join(sorted(clash))} proposed, generated or amended {atom.id}")
        unauthorized = sorted(a.id for a in approvers.values() if not a.has(*_APPROVAL_ROLES))
        if unauthorized:
            raise NotAuthorized(f"{', '.join(unauthorized)} may not approve {atom.id}")
        if atom.risk_tier >= RiskTier.HIGH:
            humans = [a for a in approvers.values() if a.is_human]
            if len(humans) < 2:
                raise NotAuthorized(f"{atom.risk_tier.name} needs two distinct human approvers")
        if atom.risk_tier == RiskTier.REGULATORY and not any(a.has(Role.SIGNATORY) for a in approvers.values()):
            raise NotAuthorized("REGULATORY needs a named signatory among the approvers")

    def transition(self, atom_id: str, to: State, actor: Actor, rationale: str) -> Optional[CascadeManifest]:
        """Public single-actor transition (disputes, retractions, demotions)."""
        if to in (State.PROBATION, State.CANONICAL):
            raise NotAuthorized("approval goes through review(), resolve_dispute() or the probation clock")
        atom = self._require(atom_id)
        if atom.state is State.RETRACTED:
            raise NotAuthorized("un-retract goes through unretract()")
        return self._transition(atom, to, actor, rationale)

    def _transition(self, atom: Atom, to: State, actor: Actor, rationale: str, *,
                    approvers: Optional[dict[str, Actor]] = None, cascade: bool = True) -> Optional[CascadeManifest]:
        frm = atom.state
        if to not in LEGAL_TRANSITIONS[frm]:
            raise IllegalTransition(f"{atom.id}: {frm.value} -> {to.value} is not a legal transition")
        if not rationale or not rationale.strip():
            raise TrustError("a transition needs a rationale")
        self._authorize(actor, atom, frm, to)
        if not actor.has(Role.SYSTEM) and actor.id in atom.authors and to in (State.PROBATION, State.CANONICAL):
            raise SelfApproval(f"{actor.id} cannot approve an atom they proposed, generated or amended")
        approving = to in (State.PROBATION, State.CANONICAL) and not actor.has(Role.SYSTEM)
        approved = dict(approvers or ({actor.id: actor} if approving else {}))
        if approving:
            self._check_approvers(atom, approved)

        now = self.clock()
        self._seq += 1
        entry = HistoryEntry(frm, to, actor.id, rationale, now, tuple(sorted(approved)), seq=self._seq)
        atom.state_history.append(entry)
        atom.state = to
        atom.entered_state_at = now
        atom.pending_approvals.clear()
        if to is State.CANONICAL:
            atom.canonical_since = now
        if to in (State.PROBATION, State.CANONICAL) and approved:
            atom.stale, atom.stale_reason = False, ""
        task = self.reviews.get(atom.id)
        if task and task.closed_at is None and to is not State.QUARANTINED:
            task.closed_at = now
        self.ledger.append("transition", atom=atom.id, frm=frm.value, to=to.value, actor=actor.id,
                           approvers=list(entry.approvers), rationale=rationale, ts=now, seq=self._seq)
        if to in CASCADE_STATES and cascade:
            return self._cascade(atom, to)
        return None

    # -------------------------------------------------------------- cascade

    def descendants(self, atom_id: str) -> list[str]:
        """Transitive closure over derived_from, in breadth-first order, root excluded."""
        seen: set[str] = {atom_id}
        order: list[str] = []
        frontier = deque([atom_id])
        while frontier:
            for child in sorted(self.children.get(frontier.popleft(), ())):
                if child not in seen:
                    seen.add(child)
                    order.append(child)
                    frontier.append(child)
        return order

    def _cascade(self, root: Atom, cause: State) -> CascadeManifest:
        started = self.clock()
        closure = self.descendants(root.id)
        summaries = tuple(d for d in closure if self.atoms[d].kind == "summary")
        disputed = []
        for d_id in closure:
            d = self.atoms[d_id]
            d.stale = True
            d.stale_reason = f"ancestor {root.id} {cause.value}"
            if d.state in (State.CANONICAL, State.PROBATION):
                # cascade=False: the closure above already covers d's descendants.
                self._transition(d, State.DISPUTED, SYSTEM, f"ancestor({root.id}) {cause.value}", cascade=False)
                disputed.append(d_id)

        affected = {root.id, *closure}
        hit = [u for u in self.use_cases.values() if u.depends_on & affected]
        production = []
        report = {"root": root.id, "cause": cause.value, "descendants": len(closure),
                  "summaries": len(summaries), "disputed": len(disputed)}
        for use_case in hit:
            self.outbox.append(Notification(use_case.owner, use_case.id, dict(report)))
            if use_case.in_production:
                production.append(use_case.id)
                self.revalidations.append(Revalidation(use_case.id, root.id, started, started + RETRO_REVIEW_WINDOW))

        manifest = CascadeManifest(root.id, cause, tuple(closure), summaries, tuple(disputed),
                                   tuple(u.id for u in hit), tuple(production), started, self.clock())
        self.cascades.append(manifest)
        self.ledger.append("cascade", root=root.id, cause=cause.value, descendants=len(closure),
                           summaries=len(summaries), disputed=list(disputed), use_cases=list(manifest.use_cases),
                           production_use_cases=production, ts=manifest.finished_at)
        return manifest

    # --------------------------------------------------------------- review

    def review_packet(self, atom_id: str) -> ReviewPacket:
        atom = self._require(atom_id)
        radius = tuple(self.descendants(atom_id))
        affected = {atom_id, *radius}
        use_cases = tuple(sorted(u.id for u in self.use_cases.values() if u.depends_on & affected))
        conflicts = tuple(sorted(
            other.id for other in self.atoms.values()
            if atom.key and other.key == atom.key and other.id != atom_id and other.content != atom.content
            and other.state not in (State.DEMOTED, State.RETRACTED)
        ))
        task = self.reviews.get(atom_id)
        body = {"atom": atom_id, "version": atom.version, "content": atom.content, "evidence": list(atom.evidence),
                "provenance": atom.provenance, "radius": list(radius), "use_cases": list(use_cases),
                "conflicts": list(conflicts), "appeal": list(task.appeal_evidence) if task else []}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        return ReviewPacket(atom_id, atom.version, atom.content, atom.evidence, atom.provenance,
                            radius, use_cases, conflicts, digest)

    def review(self, atom_id: str, reviewer: Actor, decision: str, rationale: str,
               packet: ReviewPacket, edits: Optional[dict] = None) -> str:
        """Apply one reviewer's decision. Returns what happened.

        APPROVE on HIGH+ records a pending approval until a second, distinct human
        approves; only then does the atom enter probation.
        """
        atom = self._require(atom_id)
        task = self.reviews.get(atom_id)
        if task is None or task.closed_at is not None:
            raise TrustError(f"{atom_id} has no open review")
        if atom.state not in (State.PROPOSED, State.QUARANTINED):
            raise IllegalTransition(f"{atom_id} is {atom.state.value}; nothing to review")
        if packet.digest != self.review_packet(atom_id).digest:
            raise StaleReviewPacket("the atom, its blast radius or its conflicts changed since this packet was built")
        if reviewer.id in atom.authors:
            raise SelfApproval(f"{reviewer.id} proposed, generated or amended {atom_id}")
        if decision.upper() == "APPROVE" and not reviewer.has(*_APPROVAL_ROLES):
            raise NotAuthorized(f"{reviewer.id} may not approve {atom_id}")
        if task.human_required and not reviewer.is_human:
            raise NotAuthorized(f"{atom_id} needs a human reviewer")
        if task.second_line_required and not reviewer.has(Role.SECOND_LINE):
            raise NotAuthorized(f"{atom_id} is an appeal; it needs a second-line reviewer")
        if not rationale or not rationale.strip():
            raise TrustError("a review needs a rationale")

        decision = decision.upper()
        now = self.clock()
        if decision == "APPROVE":
            atom.pending_approvals[reviewer.id] = reviewer
            approvers = dict(atom.pending_approvals)
            humans = [a for a in approvers.values() if a.is_human]
            enough = (not task.dual_control or len(humans) >= 2) and (
                not task.signatory_required or any(a.has(Role.SIGNATORY) for a in approvers.values()))
            if not enough:
                self.ledger.append("approval_pending", atom=atom_id, approver=reviewer.id, ts=now)
                return "awaiting_second_approver" if task.dual_control and len(humans) < 2 else "awaiting_signatory"
            self._transition(atom, State.PROBATION, reviewer, rationale, approvers=approvers)
            self._finish_appeal(atom, task)
            return "probation"
        if decision == "REJECT":
            self._transition(atom, State.DEMOTED, reviewer, rationale)
            self._finish_appeal(atom, task)
            return "demoted"
        if decision == "AMEND":
            if not edits or not str(edits.get("provenance", "")).strip():
                raise TrustError("an amendment must restamp provenance")
            for name in ("content", "evidence", "provenance", "derived_from"):
                if name in edits:
                    value = tuple(edits[name]) if name in ("evidence", "derived_from") else edits[name]
                    setattr(atom, name, value)
            if "derived_from" in edits:
                for parent_children in self.children.values():
                    parent_children.discard(atom.id)
                self._index_lineage(atom)
            atom.version += 1
            atom.amenders.add(reviewer.id)
            atom.pending_approvals.clear()
            self.ledger.append("amended", atom=atom_id, by=reviewer.id, version=atom.version,
                               provenance=atom.provenance, rationale=rationale, ts=now)
            return "amended_awaiting_review"
        if decision == "ESCALATE":
            atom.risk_tier = RiskTier.REGULATORY
            atom.pending_approvals.clear()
            self._route(atom, now, second_line=task.second_line_required, appeal_evidence=task.appeal_evidence)
            self.ledger.append("escalated", atom=atom_id, by=reviewer.id, rationale=rationale, ts=now)
            return "escalated"
        raise TrustError(f"unknown decision {decision!r}")

    def _finish_appeal(self, atom: Atom, task: ReviewTask) -> None:
        if task.second_line_required and atom.appeal_count >= MAX_APPEALS:
            atom.appeal_final = True
            self.ledger.append("appeal_final", atom=atom.id, ts=self.clock())

    # ----------------------------------------------------- disputes, serving

    def raise_dispute(self, atom_id: str, actor: Actor, rationale: str) -> Optional[CascadeManifest]:
        atom = self._require(atom_id)
        if atom.state not in (State.CANONICAL, State.PROBATION):
            raise IllegalTransition(f"{atom_id} is {atom.state.value}; only probation or canonical atoms are disputed")
        atom.disputes += 1
        return self._transition(atom, State.DISPUTED, actor, rationale)

    def resolve_dispute(self, atom_id: str, outcome: State, approvers: Iterable[Actor], rationale: str
                        ) -> Optional[CascadeManifest]:
        atom = self._require(atom_id)
        if atom.state is not State.DISPUTED:
            raise IllegalTransition(f"{atom_id} is not disputed")
        people = {a.id: a for a in approvers}
        if not people:
            raise NotAuthorized("a dispute is resolved by at least one person")
        lead = next(iter(people.values()))
        if outcome is State.CANONICAL:
            return self._transition(atom, State.CANONICAL, lead, rationale, approvers=people)
        return self._transition(atom, outcome, lead, rationale)

    def record_serve(self, atom_id: str, correct: bool) -> None:
        if not correct:
            self._require(atom_id).incorrect_serves += 1

    def record_output(self, output_id: str, atom_ids: Iterable[str], ts: Optional[int] = None) -> None:
        self.outputs.append(Output(output_id, frozenset(atom_ids), self.clock() if ts is None else ts))

    def record_citation(self, atom_id: str, as_fact: bool) -> None:
        self.citations.append(Citation(atom_id, as_fact, self._require(atom_id).state))

    # ------------------------------------------------------- clock-driven

    def tick(self) -> dict[str, list[str]]:
        """Run the time-based rules once. Returns atom ids per action taken."""
        now = self.clock()
        done: dict[str, list[str]] = {"canonical": [], "probation_failed": [], "quarantine_expired": [],
                                      "degraded_quarantine": []}
        for atom in list(self.atoms.values()):
            ttl = STATES[atom.state].ttl_seconds
            if atom.state is State.PROBATION and now - atom.entered_state_at >= ttl:
                if not atom.stale and atom.disputes == 0 and atom.incorrect_serves == 0:
                    self._transition(atom, State.CANONICAL, SYSTEM, "probation complete")
                    done["canonical"].append(atom.id)
                else:
                    self._transition(atom, State.DEMOTED, SYSTEM, "probation failed")
                    done["probation_failed"].append(atom.id)
            elif atom.state is State.QUARANTINED and now - atom.entered_state_at >= ttl:
                self._transition(atom, State.DEMOTED, SYSTEM, "quarantine expired without review")
                done["quarantine_expired"].append(atom.id)
            elif atom.state is State.PROPOSED:
                task = self.reviews.get(atom.id)
                if task and task.closed_at is None and now > task.due_at:
                    # Degraded mode: a backlog yields visible provisionality, never authority.
                    self._transition(atom, State.QUARANTINED, SYSTEM, "review overdue: degraded mode")
                    done["degraded_quarantine"].append(atom.id)
        return done

    # ------------------------------------------- retroactive demotion, appeal

    def canonical_window(self, atom_id: str) -> Optional[tuple[int, int]]:
        """(start, end) of the most recent canonical period; end is now if still canonical."""
        start = end = None
        for entry in self._require(atom_id).state_history:
            if entry.to_state is State.CANONICAL:
                start, end = entry.ts, None
            elif entry.from_state is State.CANONICAL and start is not None:
                end = entry.ts
        if start is None:
            return None
        return start, self.clock() if end is None else end

    def retroactive_demote(self, atom_id: str, actor: Actor, rationale: str) -> CascadeManifest:
        if not actor.has(*_RETRO_ROLES):
            raise NotAuthorized(f"{actor.id} may not retroactively demote")
        atom = self._require(atom_id)
        window = self.canonical_window(atom_id)
        manifest = self._transition(atom, State.DEMOTED, actor, rationale)
        assert manifest is not None
        sampled: list[str] = []
        if window and window[1] - window[0] > LONG_CANONICAL:
            affected = {atom_id, *manifest.descendants}
            in_window = [o for o in self.outputs if o.atom_ids & affected and window[0] <= o.ts <= window[1]]
            sampled = [o.id for o in in_window if _fraction(f"{atom_id}:{o.id}") < self.retro_sample_rate]
            if in_window and not sampled:
                sampled = [in_window[0].id]
            self.recheck_queue.extend((o, atom_id) for o in sampled)
        self.ledger.append("retroactive_demotion", atom=atom_id, actor=actor.id, rationale=rationale,
                           canonical_window=list(window) if window else None, outputs_sampled=sampled,
                           cascade_descendants=list(manifest.descendants), ts=self.clock())
        return manifest

    def appeal(self, atom_id: str, owner: Actor, evidence: Iterable[str], rationale: str) -> ReviewTask:
        atom = self._require(atom_id)
        if atom.state is not State.DEMOTED:
            raise AppealRefused(f"{atom_id} is {atom.state.value}; only demoted atoms can be appealed")
        if not owner.has(Role.DATA_OWNER):
            raise NotAuthorized("appeals come from the data owner")
        if atom.appeal_count >= MAX_APPEALS:
            # appeal_final records that the second-line decision on the last appeal stands.
            raise AppealRefused(f"{atom_id}: {MAX_APPEALS} appeals used; the second-line decision is final")
        atom.appeal_count += 1
        self._transition(atom, State.QUARANTINED, owner, f"appeal {atom.appeal_count}: {rationale}")
        return self._route(atom, self.clock(), second_line=True, appeal_evidence=tuple(evidence))

    def unretract(self, atom_id: str, approvers: Iterable[Actor], rationale: str) -> ReviewTask:
        atom = self._require(atom_id)
        if atom.state is not State.RETRACTED:
            raise IllegalTransition(f"{atom_id} is not retracted")
        people = {a.id: a for a in approvers}
        if len(people) < 2 or not all(a.has(Role.SECOND_LINE) for a in people.values()):
            raise NotAuthorized("un-retract needs two distinct second-line actors")
        if set(people) & atom.authors:
            raise SelfApproval("an author cannot un-retract their own atom")
        lead = next(iter(people.values()))
        self._transition(atom, State.QUARANTINED, lead, rationale, approvers=people)
        return self._route(atom, self.clock(), second_line=True)

    # -------------------------------------------------- use cases, outbox

    def register_use_case(self, use_case: UseCase) -> None:
        for atom_id in use_case.depends_on:
            self._require(atom_id)
        self.use_cases[use_case.id] = use_case

    def blocked(self, use_case_id: str) -> bool:
        return any(r.open for r in self.revalidations if r.use_case_id == use_case_id)

    def resolve_revalidation(self, use_case_id: str, how: str, actor: Actor) -> int:
        if how not in ("re-derived", "acknowledged"):
            raise TrustError("re-validation ends by re-derivation or acknowledgement")
        use_case = self.use_cases[use_case_id]
        if actor.id != use_case.owner and not actor.has(Role.SECOND_LINE):
            raise NotAuthorized("only the use-case owner or second line closes a re-validation")
        closed = 0
        for item in self.revalidations:
            if item.use_case_id == use_case_id and item.open:
                item.resolved_how, item.resolved_by = how, actor.id
                closed += 1
        self.ledger.append("revalidation_resolved", use_case=use_case_id, how=how, by=actor.id,
                           items=closed, ts=self.clock())
        return closed

    def deliver_notifications(self, send: Callable[[Notification], None]) -> int:
        """Try every undelivered notification once. Failures stay in the outbox."""
        sent = 0
        for note in self.outbox:
            if note.delivered:
                continue
            note.attempts += 1
            try:
                send(note)
            except Exception as exc:  # delivery is the caller's transport; record and keep
                note.last_error = f"{type(exc).__name__}: {exc}"
                continue
            note.delivered, note.last_error = True, None
            sent += 1
        return sent

    def overdue_retro_reviews(self) -> list[Revalidation]:
        now = self.clock()
        return [r for r in self.revalidations if r.open and now > r.retro_review_due]


def consolidate(fabric: TrustFabric, facts: Iterable[Atom], session: str, promote_min: float) -> list[ReviewTask]:
    """Orchestrator hook: propose extracted facts instead of writing them as truth."""
    return [fabric.propose(fact, session) for fact in facts if fact.confidence >= promote_min]
