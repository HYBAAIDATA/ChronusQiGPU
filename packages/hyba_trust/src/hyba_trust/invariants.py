"""Bypass-resistance invariants, checked over the whole fabric.

``check`` returns one message per violation; an empty list means every invariant
holds. Run it in tests and after any bulk import, since a direct write to
``fabric.atoms`` would skip the transition rules this module re-checks.
"""

from __future__ import annotations

from .fabric import MAX_APPEALS, TrustFabric
from .model import CASCADE_STATES, RiskTier, State


def check(fabric: TrustFabric) -> list[str]:
    problems: list[str] = []
    for atom in fabric.atoms.values():
        history = atom.state_history
        approvals = [e for e in history if e.to_state in (State.PROBATION, State.CANONICAL) and e.approvers]
        forbidden = {atom.proposer, atom.generating_agent} | atom.amenders

        # 1. No canonical atom without an approval record.
        if atom.state is State.CANONICAL and not approvals:
            problems.append(f"{atom.id}: canonical without an approval record")

        for e in approvals:
            # 2. No self-approval.
            if set(e.approvers) & forbidden:
                problems.append(f"{atom.id}: self-approval by {sorted(set(e.approvers) & forbidden)} (seq {e.seq})")
            # 3. Dual control on HIGH+.
            if atom.risk_tier >= RiskTier.HIGH and len(set(e.approvers)) < 2:
                problems.append(f"{atom.id}: {atom.risk_tier.name} approved by fewer than two people (seq {e.seq})")

        for e in history:
            # 5. Degraded mode never grants authority: the system only reaches
            # canonical by completing probation, and never grants probation.
            if e.actor == "system" and e.to_state is State.PROBATION:
                problems.append(f"{atom.id}: system granted probation (seq {e.seq})")
            if e.actor == "system" and e.to_state is State.CANONICAL and e.from_state is not State.PROBATION:
                problems.append(f"{atom.id}: system reached canonical from {e.from_state} (seq {e.seq})")

        # 6. Appeals are capped.
        if atom.appeal_count > MAX_APPEALS:
            problems.append(f"{atom.id}: {atom.appeal_count} appeals (cap {MAX_APPEALS})")

    # 4. Cascade completeness: after an atom enters a cascade state, no descendant
    # is authoritative unless a person re-approved it after that point.
    for root in fabric.atoms.values():
        entries = [e for e in root.state_history if e.to_state in CASCADE_STATES]
        if not entries or root.state not in CASCADE_STATES:
            continue
        since = entries[-1].seq
        for d_id in fabric.descendants(root.id):
            d = fabric.atoms[d_id]
            if not d.authoritative:
                continue
            reapproved = any(e.seq > since and e.approvers and e.to_state in (State.PROBATION, State.CANONICAL)
                             for e in d.state_history)
            if not reapproved:
                problems.append(f"{d_id}: {d.state.value} although ancestor {root.id} is {root.state.value}")
    return problems
