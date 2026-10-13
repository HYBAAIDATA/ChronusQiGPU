"""Search API: the canonical interface between intelligence and the topology.

The intelligence layer calls ``find`` / ``verify`` / ``navigate`` /
``expand`` / ``search_and_retrieve`` / ``search_or_create``. The API
compiles intents to vectors, runs the Poincaré–Cassini engine, and fetches
payloads through the manifold's anchor index and Zeckendorf expansion.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: poincare_cassini_search + hardened_unified_substrate

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from .hardened_unified_substrate import (
        ManifoldCurvature,
    )
except ImportError:  # pragma: no cover - top-level script use
    from hardened_unified_substrate import (
        ManifoldCurvature,
    )

from .intent_compiler import Intent, IntentCompiler
from .poincare_cassini_search import (
    DodecaIcosahedron32,
    PoincareCassiniSearch,
    SearchResult,
)

LUCAS_ANCHORS = (2, 1, 3, 4, 7, 11, 18, 29, 47, 76)


@dataclass
class SearchResponse:
    """Response from the search API."""

    found: bool
    anchor: Optional[int]
    payload: Optional[bytes]
    path: List[int]
    distance: float
    iterations: int
    converged: bool
    cassini_valid: bool
    precision: float
    healed_anchors: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "found": self.found,
            "anchor": self.anchor,
            "path": list(self.path),
            "distance": self.distance,
            "iterations": self.iterations,
            "converged": self.converged,
            "cassini_valid": self.cassini_valid,
            "precision": self.precision,
            "healed_anchors": list(self.healed_anchors),
            "has_payload": self.payload is not None,
        }


class SearchAPI:
    """The search API. Intelligence calls this; the topology does the work."""

    def __init__(self, manifold, epsilon: float = 1e-8):
        self.manifold = manifold
        self.overlay = DodecaIcosahedron32()
        self.engine = PoincareCassiniSearch(self.overlay, manifold=manifold, epsilon=epsilon)
        self.compiler = IntentCompiler(manifold)

    # ------------------------------------------------------------------
    # Primary operations
    # ------------------------------------------------------------------

    def find(self, features: Dict[str, float]) -> SearchResponse:
        """Find a state by semantic features."""
        intent = Intent(intent_type="find", payload={"features": features})
        target = self.compiler.compile(intent)
        result = self.engine.search(target)
        return self._to_response(result)

    def verify(self, anchor: int) -> bool:
        """Verify that an anchor satisfies the Cassini invariant."""
        return bool(self.manifold.gpu.verify_cassini_invariant(int(anchor)))

    def navigate(self, from_anchor: int, to_anchor: int) -> SearchResponse:
        """Navigate from one anchor to another along the geodesic."""
        result = self.engine.navigate(int(from_anchor), int(to_anchor))
        return self._to_response(result)

    def expand(self, from_anchor: int) -> int:
        """Grow the manifold at the next anchor after ``from_anchor``."""
        next_anchor = self._next_lucas_anchor(int(from_anchor))
        node = self.manifold.expand_manifold(next_anchor)
        return node.integer_anchor

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    def search_and_retrieve(self, features: Dict[str, float]) -> Optional[bytes]:
        """Find a state and return its stored payload, if any."""
        response = self.find(features)
        if not response.found or response.anchor is None:
            return None
        return self._fetch_by_anchor(response.anchor)

    def search_or_create(self, features: Dict[str, float], create_payload: bytes) -> int:
        """Find a state; if absent, ingest ``create_payload`` and return its anchor."""
        response = self.find(features)
        if response.found and response.anchor is not None and response.payload:
            return response.anchor
        uid = self.manifold.ingest_sync(create_payload, curvature=ManifoldCurvature.GOLDEN_DENSE)
        return self.manifold.tensors[uid].integer_anchor

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_response(self, result: SearchResult) -> SearchResponse:
        anchor = result.target_anchor if result.converged else None
        return SearchResponse(
            found=result.converged,
            anchor=anchor,
            payload=self._fetch_by_anchor(anchor) if anchor is not None else None,
            path=result.path,
            distance=result.total_distance,
            iterations=result.iterations,
            converged=result.converged,
            cassini_valid=result.cassini_valid,
            precision=result.final_precision,
            healed_anchors=result.healed_anchors,
        )

    def _fetch_by_anchor(self, anchor: Optional[int]) -> Optional[bytes]:
        if anchor is None:
            return None
        tensor = self.manifold.get_by_anchor(anchor)
        if tensor is None:
            return None
        return self.manifold.read_payload(tensor)

    def _next_lucas_anchor(self, current: int) -> int:
        for lucas in LUCAS_ANCHORS:
            if lucas > current:
                return lucas
        candidate = (current * 2) % 90
        if candidate <= 0 or candidate == current:
            candidate = (current + 1) % 90 or 1
        return candidate


__all__ = ["SearchAPI", "SearchResponse", "LUCAS_ANCHORS"]
