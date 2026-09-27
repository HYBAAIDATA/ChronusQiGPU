"""Neural plasticity wired to the search topology.

Subsystems co-activate along discovered geodesic paths: the search engine
finds the path between two anchored states, then Hebbian reinforcement
(strength by reward) wires the traversed anchor pairs together.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: search_api + neural_plasticity

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .neural_plasticity import NeuralPlasticity
from .search_api import SearchAPI


class PlasticitySearch:
    """Pathway discovery through the manifold + plastic reinforcement."""

    def __init__(self, manifold):
        self.manifold = manifold
        self.search = SearchAPI(manifold)
        self.plasticity = NeuralPlasticity()

    def discover_pathway(
        self,
        pre_features: Dict[str, float],
        post_features: Dict[str, float],
    ) -> Optional[List[int]]:
        """Find the geodesic path between two subsystem states."""
        pre_response = self.search.find(pre_features)
        if not pre_response.found or pre_response.anchor is None:
            return None
        post_response = self.search.find(post_features)
        if not post_response.found or post_response.anchor is None:
            return None
        nav = self.search.navigate(pre_response.anchor, post_response.anchor)
        return nav.path if nav.found else None

    def reinforce_pathway(self, path: List[int], reward: float) -> None:
        """Hebbian-reinforce every consecutive anchor pair along a path."""
        for i in range(len(path) - 1):
            self.plasticity.co_activate(f"anchor_{path[i]}", f"anchor_{path[i + 1]}")
        self.plasticity.deliver_reward(reward)

    def report(self) -> Dict[str, Any]:
        return self.plasticity.report()


__all__ = ["PlasticitySearch"]
