"""Mining Bridge: Wire the Poincare-Cassini search ontology to mining strategy.

Evaluates candidate nonces against Lucas 15 attractor resonance, deciding
structured search (Poincare-Cassini geodesic pathfinder) vs unstructured
search (Grover amplitude amplification / quantum walk).
"""

# LUCAS WIRING: wiring layer -- composes the Lucas attractor, pathfinder,
# and database into mining strategy selection.
# Substrate route: mining

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from .lucas_attractor import LucasAttractor
from .pathfinder import Pathfinder
from .search_database import SearchDatabase


@dataclass
class MiningDecision:
    """Decision for mining strategy selection."""

    strategy: str
    confidence: float
    lucas_attractor: float
    nonce_resonance: float
    rationale: str
    theorem_proven: bool = False
    claim_boundary: str = (
        "Algorithmic search-space ordering based on Lucas 15 attractor resonance; "
        "no consensus bypass or unverified PoW advantage is asserted."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "confidence": self.confidence,
            "lucas_attractor": self.lucas_attractor,
            "nonce_resonance": self.nonce_resonance,
            "rationale": self.rationale,
            "theorem_proven": self.theorem_proven,
            "claim_boundary": self.claim_boundary,
        }


class MiningBridge:
    """Mining bridge connecting the ontology to mining strategies."""

    def __init__(
        self,
        attractor: Optional[LucasAttractor] = None,
        pathfinder: Optional[Pathfinder] = None,
        database: Optional[SearchDatabase] = None,
    ) -> None:
        self.attractor = attractor or LucasAttractor(n=15)
        self.pathfinder = pathfinder or Pathfinder(n_faces=32)
        self.database = database or SearchDatabase(n_anchors=90)

    def decide(self, nonce: int) -> MiningDecision:
        """Decide structured vs unstructured search for a candidate nonce."""
        n = int(nonce)
        lucas_score = self.attractor.total_score(n)
        nonce_resonance = self._nonce_resonance(n)
        if lucas_score > 0.5 and nonce_resonance > 0.5:
            strategy = "structured"
            confidence = (lucas_score + nonce_resonance) / 2.0
            rationale = f"Nonce {n} resonates with Lucas 15 attractor (score: {lucas_score:.4f})"
        else:
            strategy = "unstructured"
            confidence = 1.0 - (lucas_score + nonce_resonance) / 2.0
            rationale = f"Nonce {n} uniform; dispatching Grover unstructured walk"
        return MiningDecision(
            strategy=strategy,
            confidence=float(np.clip(confidence, 0.0, 1.0)),
            lucas_attractor=lucas_score,
            nonce_resonance=nonce_resonance,
            rationale=rationale,
        )

    def _nonce_resonance(self, nonce: int) -> float:
        zeck = self._zeckendorf(nonce)
        target_len = len(self.attractor.zeckendorf)
        sparsity = 1.0 / (1.0 + abs(len(zeck) - target_len))
        phi_res = self.attractor.phi_resonance(float(nonce))
        return float((sparsity + phi_res) / 2.0)

    @staticmethod
    def _zeckendorf(n: int) -> List[int]:
        target = int(abs(n))
        if target == 0:
            return []
        fibs = [1, 2]
        while fibs[-1] < target:
            fibs.append(fibs[-1] + fibs[-2])
        result = []
        for f in reversed(fibs):
            if f <= target:
                result.append(f)
                target -= f
        return result

    def mine_structured(self, nonces: List[int], target: float) -> Dict[str, Any]:
        """Structured search via Poincare-Cassini ontology."""
        r0 = self.pathfinder._anchor_to_vector(15)
        result = self.pathfinder.navigate(r0, float(target))
        node = self.database.query(float(target))
        return {
            "strategy": "structured",
            "iterations": result["iterations"],
            "precision": result["final_precision"],
            "lucas_score": result["lucas_score"],
            "database_node": node,
            "converged": result["converged"],
            "claim_boundary": "Structured geodesic search on state manifold",
            "theorem_proven": False,
        }

    def mine_unstructured(self, nonces: List[int], target: float) -> Dict[str, Any]:
        """Unstructured search via Grover amplitude amplification."""
        N = max(1, len(nonces))
        arg = min(1.0, 1.0 / math.sqrt(N))
        asin_val = math.asin(arg)
        k_opt = int(math.floor(math.pi / (4.0 * asin_val))) if asin_val > 0 else 1
        return {
            "strategy": "unstructured",
            "iterations": max(1, k_opt),
            "N": N,
            "claim_boundary": "Unstructured search ceiling (Grover)",
            "theorem_proven": False,
        }

    def mine(self, nonces: List[int], target: float) -> Dict[str, Any]:
        """Mine nonces via appropriate strategy."""
        if not nonces:
            return self.mine_unstructured([0], target)
        decision = self.decide(nonces[0])
        out = (
            self.mine_structured(nonces, target)
            if decision.strategy == "structured"
            else self.mine_unstructured(nonces, target)
        )
        out["decision"] = decision.to_dict()
        return out


__all__ = ["MiningBridge", "MiningDecision"]
