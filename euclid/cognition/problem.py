"""Typed problem envelope for the canonical EUCLID cognition loop.

The envelope makes goals, measured reward, objectives and authority explicit.
It is domain-neutral; specialist domains may wrap it but cannot gain authority
merely by becoming a cognition problem.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from euclid.contracts import RewardAuthority, domain_hash


@dataclass(frozen=True)
class CognitionObjective:
    objective_id: str
    metric: str
    direction: str
    target: float | None = None
    weight: float = 1.0
    authority: str = "advisory"

    def __post_init__(self) -> None:
        if not self.objective_id or not self.metric:
            raise ValueError("objective identity and metric are required")
        if self.direction not in {"maximize", "minimize", "hold"}:
            raise ValueError("objective direction must be maximize, minimize or hold")
        if self.target is not None and not math.isfinite(float(self.target)):
            raise ValueError("objective target must be finite")
        if not math.isfinite(float(self.weight)) or float(self.weight) < 0:
            raise ValueError("objective weight must be finite and non-negative")


@dataclass(frozen=True)
class CognitionProblem:
    problem_id: str
    goal: str
    problem_class: str
    structure: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    objectives: tuple[CognitionObjective, ...] = ()
    measured_reward: float | None = None
    reward_authority: RewardAuthority = RewardAuthority.NONE
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem_id or not self.goal or not self.problem_class:
            raise ValueError("problem identity, goal and class are required")
        if self.measured_reward is not None and not math.isfinite(float(self.measured_reward)):
            raise ValueError("measured reward must be finite")
        if self.reward_authority is RewardAuthority.NONE and self.measured_reward is not None:
            raise ValueError("reward cannot exist without an authority")
        if self.reward_authority is not RewardAuthority.NONE and self.measured_reward is None:
            raise ValueError("reward authority requires a measured reward")

    @property
    def digest(self) -> str:
        return domain_hash(
            "euclid.cognition.problem.v1",
            {
                "problem_id": self.problem_id,
                "goal": self.goal,
                "problem_class": self.problem_class,
                "structure": self.structure,
                "observations": self.observations,
                "objectives": [
                    {
                        "objective_id": o.objective_id,
                        "metric": o.metric,
                        "direction": o.direction,
                        "target": o.target,
                        "weight": o.weight,
                        "authority": o.authority,
                    }
                    for o in self.objectives
                ],
                "measured_reward": self.measured_reward,
                "reward_authority": self.reward_authority.value,
                "constraints": dict(self.constraints),
                "metadata": dict(self.metadata),
            },
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "goal": self.goal,
            "problem_class": self.problem_class,
            "structure": list(self.structure),
            "observations": list(self.observations),
            "declared_objectives": [
                {
                    "objective_id": o.objective_id,
                    "metric": o.metric,
                    "direction": o.direction,
                    "target": o.target,
                    "weight": o.weight,
                    "authority": o.authority,
                }
                for o in self.objectives
            ],
            "measured_reward": self.measured_reward,
            "reward_authority": self.reward_authority.value,
            "constraints": dict(self.constraints),
            "problem_digest": self.digest,
            **dict(self.metadata),
        }


__all__ = ["CognitionObjective", "CognitionProblem"]
