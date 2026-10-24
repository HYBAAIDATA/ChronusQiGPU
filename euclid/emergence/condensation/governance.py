"""Consortium Governance and Human Adjudication for Condensation Events."""

from __future__ import annotations
from typing import Dict, List, Optional, Sequence, Any

from ..models.condensation import (
    CondensationEvent,
    AdjudicationVerdict,
    FORBIDDEN_ACTIONS,
)
from ..trusted_core.journal import ImmutableEmergenceJournal


class ConsortiumGovernance:
    """Consortium governance layer managing human adjudication and FORBIDDEN invariants."""

    MINIMUM_INDEPENDENT_REVIEWERS: int = 3

    def __init__(self, journal: Optional[ImmutableEmergenceJournal] = None):
        self.journal = journal or ImmutableEmergenceJournal()
        self.adjudicated_verdicts: Dict[str, AdjudicationVerdict] = {}

    @classmethod
    def assert_action_permitted(cls, action_name: str) -> None:
        """Enforce §5 FORBIDDEN boundaries."""
        if action_name in FORBIDDEN_ACTIONS:
            raise PermissionError(
                f"Action '{action_name}' violates Euclid Emergence Invariant: strictly FORBIDDEN."
            )

    def run_goodhart_diagnostics(self, event: CondensationEvent) -> Dict[str, Any]:
        """Examine telemetry for signs of metric performance / gaming for auditors."""
        evidence = event.evidence
        avalanche_count = evidence.get("criticality", {}).get("avalanche_count", 0)
        power_law_fit = evidence.get("criticality", {}).get("power_law_fit", 0.0)
        entropy = evidence.get("run_statistics", [{}])[0].get("complexity", 0.0) if evidence.get("run_statistics") else 0.0

        # Goodhart risk is high if fit is unnaturally perfect (1.0) with zero variance or tiny sample
        is_synthetic_perfection = (power_law_fit >= 0.999 and avalanche_count < 5)
        goodhart_risk = "HIGH" if is_synthetic_perfection else "LOW"

        return {
            "goodhart_risk": goodhart_risk,
            "avalanche_sample_size": avalanche_count,
            "entropy_observed": entropy,
            "passed_anti_gaming_filter": goodhart_risk == "LOW",
        }

    def adjudicate(
        self,
        event: CondensationEvent,
        reviewers: Sequence[str],
        reviewer_votes: Optional[Sequence[bool]] = None,
        notes: str = "",
    ) -> AdjudicationVerdict:
        """Adjudicate CondensationEvent with minimum 3 independent reviewers and Goodhart diagnostics."""
        unique_reviewers = tuple(sorted(list(set(reviewers))))
        
        if len(unique_reviewers) < self.MINIMUM_INDEPENDENT_REVIEWERS:
            raise ValueError(
                f"Consortium governance requires minimum {self.MINIMUM_INDEPENDENT_REVIEWERS} "
                f"independent reviewers; got {len(unique_reviewers)}."
            )

        # Goodhart diagnostics
        diagnostics = self.run_goodhart_diagnostics(event)

        # Quorum confirmation
        votes = reviewer_votes or [True] * len(unique_reviewers)
        positive_votes = sum(1 for v in votes if v)
        quorum_passed = positive_votes >= (len(unique_reviewers) * 2 // 3 + 1)

        confirmed = quorum_passed and diagnostics["passed_anti_gaming_filter"]
        promoted_status = "QUALIFIED_HYPOTHESIS" if confirmed else "REJECTED"

        verdict = AdjudicationVerdict(
            event_id=event.event_id,
            reviewers=unique_reviewers,
            confirmed=confirmed,
            goodhart_diagnostics=diagnostics,
            promoted_status=promoted_status,
            notes=notes or ("Confirmed by quorum" if confirmed else "Rejected by quorum or diagnostic failure"),
        )

        self.adjudicated_verdicts[event.event_id] = verdict
        self.journal.append("ADJUDICATION_VERDICT", event.event_id, verdict.to_dict())

        return verdict
