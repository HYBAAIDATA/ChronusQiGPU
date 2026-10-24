"""Search-aware orchestrator: executes intents through the 11D topology.

Exposes ``execute_intent`` (find / verify / navigate / decide),
``search_and_ingest``, and substrate ``stats`` as the single entry point
the intelligence layer uses to drive the search topology.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: search_api + agentic_controller_search + hardened_unified_substrate

from __future__ import annotations

from typing import Any, Dict

from aethel.hardened_unified_substrate import ManifoldCurvature

from .agentic_controller_search import AgenticSearchController
from .search_api import SearchAPI


class SearchAwareOrchestrator:
    """Orchestrator that runs every intent through the search topology."""

    def __init__(self, manifold):
        self.manifold = manifold
        self.search = SearchAPI(manifold)
        self.controller = AgenticSearchController(manifold)

    async def execute_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        intent_type = intent.get("type", "find")

        if intent_type == "find":
            response = self.search.find(intent.get("features", {}))
            return {
                "found": response.found,
                "anchor": response.anchor,
                "payload": response.payload,
                "path": response.path,
                "cassini_valid": response.cassini_valid,
            }

        if intent_type == "verify":
            return {"valid": self.search.verify(intent.get("anchor", 1))}

        if intent_type == "navigate":
            response = self.search.navigate(
                intent.get("from_anchor", 1), intent.get("to_anchor", 1)
            )
            return {
                "arrived": response.found,
                "anchor": response.anchor,
                "path": response.path,
                "distance": response.distance,
            }

        if intent_type == "decide":
            return self.controller.decide(intent.get("context", {}))

        return {"error": f"unknown intent type: {intent_type}"}

    async def search_and_ingest(self, features: Dict[str, float], payload: bytes) -> Dict[str, Any]:
        """Search for a state; if absent, ingest the payload."""
        response = self.search.find(features)
        if response.found:
            return {"found": True, "anchor": response.anchor}
        uid = self.manifold.ingest_sync(payload, curvature=ManifoldCurvature.GOLDEN_DENSE)
        tensor = self.manifold.tensors[uid]
        return {
            "found": False,
            "created": True,
            "anchor": tensor.integer_anchor,
            "uuid": uid,
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "manifold_tensors": len(self.manifold.tensors),
            "anchor_index": len(self.manifold.anchor_index),
            "current_anchor": self.controller.current_anchor,
            "state_history_length": len(self.controller.state_history),
            "heal_events": len(self.manifold.self_healing.heal_log),
        }


__all__ = ["SearchAwareOrchestrator"]
