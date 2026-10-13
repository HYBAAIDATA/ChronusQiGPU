"""Agentic controller wired to the 11D search topology.

The controller's decision space is the manifold: decisions are anchors,
navigation is geodesic traversal, and state validity is the Cassini
invariant. ``decide`` reuses a matching state when the search finds one
and creates a new anchored state when it does not.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: search_api + hardened_unified_substrate

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

try:
    from .hardened_unified_substrate import ManifoldCurvature
except ImportError:  # pragma: no cover - top-level script use
    from hardened_unified_substrate import ManifoldCurvature

from .search_api import SearchAPI


class AgenticSearchController:
    """Agentic controller whose decisions live on the search manifold."""

    def __init__(self, manifold):
        self.manifold = manifold
        self.search = SearchAPI(manifold)
        self.current_anchor: Optional[int] = None
        self.state_history: List[int] = []

    def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Decide via search: reuse a matching state or create a new one."""
        features = self._extract_features(context)
        response = self.search.find(features)

        if response.found and response.anchor is not None and response.payload:
            return {
                "decision": "reuse",
                "anchor": response.anchor,
                "payload": response.payload,
                "confidence": max(0.0, 1.0 - response.precision),
                "path": response.path,
                "cassini_valid": response.cassini_valid,
            }

        new_anchor = self.search.expand(self.current_anchor or 1)
        payload = self._serialize_decision(context, new_anchor)
        uid = self.manifold.ingest_sync(payload, curvature=ManifoldCurvature.GOLDEN_DENSE)
        stored_anchor = self.manifold.tensors[uid].integer_anchor
        self.current_anchor = stored_anchor
        self.state_history.append(stored_anchor)
        return {
            "decision": "create",
            "anchor": stored_anchor,
            "expanded_anchor": new_anchor,
            "payload": payload,
            "confidence": 0.5,
        }

    def navigate_to(self, target_anchor: int) -> Dict[str, Any]:
        """Traverse from the current state to ``target_anchor``."""
        if self.current_anchor is None:
            self.current_anchor = 1
        response = self.search.navigate(self.current_anchor, target_anchor)
        if response.found and response.anchor is not None:
            self.current_anchor = response.anchor
            self.state_history.append(response.anchor)
        return {
            "arrived": response.found,
            "current_anchor": self.current_anchor,
            "path": response.path,
            "distance": response.distance,
            "cassini_valid": response.cassini_valid,
        }

    def verify_state(self, anchor: Optional[int] = None) -> bool:
        """Cassini-verify the current (or given) state's anchor."""
        target = anchor if anchor is not None else self.current_anchor
        if target is None:
            return False
        return self.search.verify(target)

    def _extract_features(self, context: Dict[str, Any]) -> Dict[str, float]:
        features: Dict[str, float] = {}
        for key, value in context.items():
            if isinstance(value, bool):
                features[key] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                features[key] = float(value)
            elif isinstance(value, str):
                features[key] = float(abs(hash(value)) % 1000) / 1000.0
        return features

    def _serialize_decision(self, context: Dict[str, Any], anchor: int) -> bytes:
        return json.dumps({"context": context, "anchor": anchor, "timestamp": time.time()}).encode(
            "utf-8"
        )


__all__ = ["AgenticSearchController"]
