"""EuclidCore measured policy selection.

The production policy is deterministic empirical selection.  It contains no
random sampling, prior distribution, or synthetic reward.  A mask can only
be preferred after observed telemetry has recorded its reward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ArmStatistics:
    observations: int = 0
    total_reward: float = 0.0

    @property
    def mean_reward(self) -> float:
        return self.total_reward / self.observations if self.observations else 0.0


class EuclidCoreBandit:
    """Deterministic measured policy over the declared mask candidates.

    The historical class name is retained for configuration compatibility;
    the implementation is no longer a bandit and does not explore by
    probability.  Unobserved arms remain at baseline and observed arms are
    selected by exact empirical mean with declaration-order tie-breaking.
    """

    CANDIDATE_MASKS = {
        "A_baseline": 0x0000FFFF,
        "B_shifted": 0x0001FFFE,
        "C_sparse": 0x00101010,
        "E_dense": 0x01110000,
    }

    def __init__(self, *, seed: int = 1517) -> None:
        self.seed = seed
        self.distributions = {arm: ArmStatistics() for arm in self.CANDIDATE_MASKS}

    def select_optimal_mask(self) -> tuple[str, int]:
        arm = max(
            self.distributions,
            key=lambda name: self.distributions[name].mean_reward,
        )
        return arm, self.CANDIDATE_MASKS[arm]

    def register_reward(self, arm: str, reward_score: float) -> None:
        if arm not in self.distributions:
            raise KeyError(arm)
        if not math.isfinite(reward_score):
            raise ValueError("reward_score must be finite")
        score = float(reward_score)
        stats = self.distributions[arm]
        stats.observations += 1
        stats.total_reward += score

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            arm: {
                "observations": stats.observations,
                "total_reward": stats.total_reward,
                "mean_reward": stats.mean_reward,
            }
            for arm, stats in self.distributions.items()
        }

    def to_dict(self) -> dict[str, Any]:
        return {"policy": "deterministic_measured", "arms": self.snapshot()}
