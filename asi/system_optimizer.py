"""ASI optimisation compatibility surface.

SALAMANDER is the sole self-healing/optimisation authority.  ASI may formulate
an optimisation proposal, but it may not claim measured impact or application.
Promotion, rollback and evidence live in the canonical Salamander policy
lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class OptimizationTarget(str, Enum):
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    EFFICIENCY = "efficiency"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    COST = "cost"


@dataclass
class OptimizationAction:
    action_id: str
    target: OptimizationTarget
    description: str
    priority: float | None = None
    estimated_impact: float | None = None
    implemented: bool = False
    evidence_ref: str | None = None
    status: str = "PROPOSED"


class SystemOptimizer:
    """Proposal-only facade; canonical optimisation is Salamander-owned."""

    def __init__(self) -> None:
        self.optimization_actions: list[OptimizationAction] = []

    @staticmethod
    def _target(value: OptimizationTarget | str) -> OptimizationTarget:
        if isinstance(value, OptimizationTarget):
            return value
        try:
            return OptimizationTarget(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"unsupported optimization target: {value}") from exc

    def analyze_system(self) -> dict[str, Any]:
        return {
            "status": "DELEGATED_TO_SALAMANDER",
            "authority": "SALAMANDER",
            "optimization_proposals": len(self.optimization_actions),
            "verified_promotions": sum(
                1 for action in self.optimization_actions if action.implemented
            ),
            "targets": [target.value for target in OptimizationTarget],
            "claim_boundary": "NO_IMPACT_WITHOUT_MEASURED_SALAMANDER_EVIDENCE",
        }

    def optimize(self, target: OptimizationTarget | str) -> OptimizationAction:
        """Create a proposal only; do not report an optimisation as applied."""
        normalized = self._target(target)
        action = OptimizationAction(
            action_id=f"opt_{len(self.optimization_actions)}",
            target=normalized,
            description=f"Propose {normalized.value} optimisation for Salamander evaluation",
        )
        self.optimization_actions.append(action)
        logger.info("Created Salamander-bound optimisation proposal %s", action.action_id)
        return action

    def record_salamander_outcome(
        self,
        action_id: str,
        outcome: Mapping[str, Any],
    ) -> OptimizationAction:
        action = next(
            (item for item in self.optimization_actions if item.action_id == action_id),
            None,
        )
        if action is None:
            raise KeyError(action_id)
        accepted = outcome.get("accepted") is True
        lifecycle = str(outcome.get("policy_lifecycle") or "")
        evidence_ref = (
            outcome.get("verifier_evidence_ref")
            or outcome.get("evidence_ref")
            or outcome.get("trial_evidence_ref")
        )
        action.evidence_ref = str(evidence_ref) if evidence_ref else None
        action.implemented = bool(
            accepted and lifecycle == "PROMOTED" and action.evidence_ref
        )
        action.status = (
            "PROMOTED_VERIFIED" if action.implemented else "NOT_PROMOTED"
        )
        return action

    def get_metrics(self) -> dict[str, Any]:
        return {
            **self.analyze_system(),
            "actions": [asdict(item) for item in self.optimization_actions[-20:]],
        }
