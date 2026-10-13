"""Ontology Mining Engine: Full integration of ontology, attractor, and mining.

Wires Poincare-Cassini ontology, Lucas 15 attractor, 32-face pathfinder,
Cassini-certified search database, and mining bridge.
"""

# LUCAS WIRING: wiring layer -- integrates the full ontology into mining.
# Substrate route: engine

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .lucas_attractor import LucasAttractor
from .mining_bridge_ontology import MiningBridge
from .pathfinder import Pathfinder
from .search_database import SearchDatabase


class OntologyMiningEngine:
    """Full ontology mining engine."""

    def __init__(
        self,
        attractor: Optional[LucasAttractor] = None,
        pathfinder: Optional[Pathfinder] = None,
        database: Optional[SearchDatabase] = None,
        bridge: Optional[MiningBridge] = None,
        manifold: Optional[Any] = None,
    ) -> None:
        self.attractor = attractor or LucasAttractor(n=15)
        self.pathfinder = pathfinder or Pathfinder(n_faces=32)
        self.database = database or SearchDatabase(n_anchors=90, manifold=manifold)
        self.bridge = bridge or MiningBridge(
            attractor=self.attractor,
            pathfinder=self.pathfinder,
            database=self.database,
        )
        self.manifold = manifold

    def mine(self, nonces: List[int], target: float) -> Dict[str, Any]:
        """Execute mining run with strategy selection."""
        if not nonces:
            nonces = [0]
        decision = self.bridge.decide(nonces[0])
        result = (
            self.bridge.mine_structured(nonces, target)
            if decision.strategy == "structured"
            else self.bridge.mine_unstructured(nonces, target)
        )
        result["attractor"] = self.attractor.state()
        result["decision"] = decision.to_dict()
        result["theorem_proven"] = False
        return result

    def benchmark(self, n_trials: int = 100) -> Dict[str, Any]:
        """Benchmark the engine across randomised nonce/target distributions."""
        trials = max(1, int(n_trials))
        structured_count = 0
        unstructured_count = 0
        total_iterations = 0
        rng = np.random.default_rng(42)
        for _ in range(trials):
            nonce = (
                int(1364 + rng.integers(-5, 6))
                if rng.random() < 0.5
                else int(rng.integers(1, 1_000_000))
            )
            target = float(rng.uniform(1.0, 1000.0))
            decision = self.bridge.decide(nonce)
            if decision.strategy == "structured":
                structured_count += 1
                res = self.bridge.mine_structured([nonce], target)
            else:
                unstructured_count += 1
                res = self.bridge.mine_unstructured([nonce], target)
            total_iterations += int(res["iterations"])
        return {
            "n_trials": trials,
            "structured_count": structured_count,
            "unstructured_count": unstructured_count,
            "avg_iterations": float(total_iterations / trials),
            "structured_pct": float(structured_count / trials * 100.0),
            "unstructured_pct": float(unstructured_count / trials * 100.0),
            "theorem_proven": False,
        }


__all__ = ["OntologyMiningEngine"]
