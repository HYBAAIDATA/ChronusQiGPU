"""Top-level shim for meta_rl module as specified in EUCLID Frontier Pseudocode."""

from euclid.cognition.frontier.meta_rl import (
    LearningRule,
    InnerState,
    Trajectory,
    BaselinePPO_rule,
    inner_rollout,
    meta_fitness,
    discover,
)

AlgorithmicDiscovery = discover

__all__ = [
    "LearningRule",
    "InnerState",
    "Trajectory",
    "BaselinePPO_rule",
    "inner_rollout",
    "meta_fitness",
    "discover",
    "AlgorithmicDiscovery",
]
