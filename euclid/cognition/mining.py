"""Mining as a bounded EUCLID cognition problem.

This adapter does not move mining authority into EUCLID. It turns measured
PYTHIA transport state into a CognitionProblem whose only admissible actuator
is dispatch breadth. PYTHIA still owns SearchPlan finalisation, complete nonce
coverage, Hendrix traversal, SHA256d/target semantics, validation, submission,
credentials and pool acknowledgement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from euclid.contracts import RewardAuthority, domain_hash
from euclid.cognition.problem import CognitionObjective, CognitionProblem


@dataclass(frozen=True)
class MiningCognitionProblem:
    problem: CognitionProblem
    baseline_dispatch_breadth: int
    current_dispatch_breadth: int
    action_breadths: Mapping[str, int]

    ACTIONS = ("hold", "reduce", "restore")

    @staticmethod
    def measured_reward(snapshot: Mapping[str, Any] | None) -> float | None:
        snap = dict(snapshot or {})
        outcomes = dict(snap.get("outcomes") or {})
        keys = ("accepted_ratio", "rejected_ratio", "unknown_ratio", "stale_ratio")
        if all(outcomes.get(key) is None for key in keys):
            return None
        accepted = float(outcomes.get("accepted_ratio") or 0.0)
        rejected = float(outcomes.get("rejected_ratio") or 0.0)
        unknown = float(outcomes.get("unknown_ratio") or 0.0)
        stale = float(outcomes.get("stale_ratio") or 0.0)
        return max(-1.0, min(1.0, accepted - rejected - unknown - stale))

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, Any] | None,
        *,
        state: Mapping[str, Any],
        baseline_dispatch_breadth: int,
        current_dispatch_breadth: int,
        recovery_mode: str | None,
        hashrate_hs: float | None,
    ) -> "MiningCognitionProblem":
        baseline = max(1, int(baseline_dispatch_breadth))
        current = max(1, min(baseline, int(current_dispatch_breadth)))
        reward = cls.measured_reward(snapshot)
        authority = (
            RewardAuthority.MEASURED_ENVIRONMENT
            if reward is not None
            else RewardAuthority.NONE
        )
        snap = dict(snapshot or {})
        counters = dict(snap.get("counters") or {})
        identity = {
            "submitted": counters.get("submitted"),
            "accepted": counters.get("accepted"),
            "rejected": counters.get("rejected"),
            "unknown": counters.get("unknown"),
            "state": dict(state),
        }
        problem_id = "mining-breadth-" + domain_hash(
            "euclid.mining-cognition.problem.v1", identity
        )[:24]
        observations = tuple(
            f"{key}={value}" for key, value in sorted(state.items())
            if value is not None
        )
        problem = CognitionProblem(
            problem_id=problem_id,
            goal=(
                "Choose bounded dispatch breadth from measured transport state "
                "without changing Bitcoin proof or PYTHIA mining authority"
            ),
            problem_class="bitcoin-mining-operating-breadth",
            structure=(
                "measured-transport",
                "bounded-dispatch-breadth",
                "pythia-final-mining-authority",
                "euclid-advisory-cognition",
            ),
            observations=observations,
            objectives=(
                CognitionObjective(
                    "accepted-share-utility",
                    "measured-share-outcome",
                    "maximize",
                    weight=0.60,
                ),
                CognitionObjective(
                    "stale-reject-unknown",
                    "transport-failure-ratio",
                    "minimize",
                    target=0.0,
                    weight=0.30,
                ),
                CognitionObjective(
                    "coverage-bound",
                    "dispatch-breadth",
                    "hold",
                    target=float(baseline),
                    weight=0.10,
                    authority="PYTHIA-bound",
                ),
            ),
            measured_reward=reward,
            reward_authority=authority,
            constraints={
                "minimum_dispatch_breadth": 1,
                "maximum_dispatch_breadth": baseline,
                "allowed_actions": list(cls.ACTIONS),
                "forbidden": [
                    "bitcoin-header",
                    "nonce-semantics",
                    "sha256d",
                    "target",
                    "share-validation",
                    "submission",
                    "credentials",
                    "pool-acknowledgement",
                ],
            },
            metadata={
                "recovery_mode": str(recovery_mode or "unknown"),
                "hashrate_hs": hashrate_hs,
                "state": dict(state),
            },
        )
        return cls(
            problem,
            baseline,
            current,
            {
                "hold": current,
                "reduce": max(1, baseline // 2),
                "restore": baseline,
            },
        )

    def breadth_for(self, action: str) -> int:
        if action not in self.ACTIONS:
            raise ValueError(f"unsupported mining cognition action: {action}")
        return max(
            1,
            min(
                self.baseline_dispatch_breadth,
                int(self.action_breadths[action]),
            ),
        )


__all__ = ["MiningCognitionProblem"]
