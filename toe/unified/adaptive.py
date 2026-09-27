"""Adaptive interface.

The profile is the user's observed actions: which widgets they open, how
deep they go, and how recently. Dashboard order follows that distribution.
Nothing here is inferred beyond the events supplied.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass
class Action:
    user: str
    widget: str
    depth: int
    at: float


@dataclass
class CognitiveProfile:
    user: str
    actions: int
    entropy: float
    preferred_density: str
    widget_rank: tuple[str, ...]
    mean_depth: float


class AdaptiveInterface:
    def __init__(self, half_life_s: float = 7 * 24 * 3600) -> None:
        self.half_life_s = half_life_s
        self._actions: dict[str, list[Action]] = {}

    def observe(self, user: str, widget: str, depth: int = 1, at: float | None = None) -> CognitiveProfile:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        action = Action(user, widget, depth, time.time() if at is None else at)
        self._actions.setdefault(user, []).append(action)
        return self.profile(user)

    def profile(self, user: str, now: float | None = None) -> CognitiveProfile:
        actions = self._actions.get(user, [])
        if not actions:
            return CognitiveProfile(user, 0, 0.0, "detailed", (), 0.0)
        now = time.time() if now is None else now
        weights: dict[str, float] = {}
        depth_sum = 0.0
        for action in actions:
            age = max(0.0, now - action.at)
            weight = 0.5 ** (age / self.half_life_s)
            weights[action.widget] = weights.get(action.widget, 0.0) + weight
            depth_sum += action.depth
        total = sum(weights.values()) or 1.0
        entropy = 0.0
        for weight in weights.values():
            share = weight / total
            if share > 0:
                entropy -= share * math.log(share)
        mean_depth = depth_sum / len(actions)
        density = "compact" if mean_depth < 2 else "detailed"
        rank = tuple(sorted(weights, key=lambda name: (-weights[name], name)))
        return CognitiveProfile(user, len(actions), entropy, density, rank, mean_depth)
