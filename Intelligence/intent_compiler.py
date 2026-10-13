"""Intent compiler: translates semantic intents into 11D search vectors.

This is the front door between the intelligence layer and the search
topology. Intelligence speaks intents (``find``, ``verify``, ``navigate``,
``expand``); the search engine speaks positions in R^11. The compiler maps
each intent to a point whose golden-weighted norm projects onto the
intended anchor lattice address.

Anchor roundtrip is exact: ``anchor_to_vector`` lifts anchor ``a`` to the
point ``(a * sqrt(phi), 0, ...)`` which projects back to ``a``. Generic
``find`` feature maps are projected through a monotone saturation
``r* = 89 * s / (1 + s)`` so every feature set lands at a deterministic
address inside the lattice range [0, 89).
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: poincare_cassini_search + hardened_unified_substrate

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from .poincare_cassini_search import (
    ANCHOR_MODULUS,
    DIM,
    PHI,
    anchor_to_vector,
    weighted_norm,
)


@dataclass
class Intent:
    """A semantic intent from the intelligence layer."""

    intent_type: str  # 'find' | 'verify' | 'navigate' | 'expand'
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: float = 1.0
    timeout_ms: int = 5000


class IntentCompiler:
    """Compiles semantic intents into 11D search vectors."""

    def __init__(self, manifold: Optional[Any] = None):
        self.manifold = manifold

    def compile(self, intent: Intent) -> np.ndarray:
        if intent.intent_type == "find":
            return self._compile_find(intent)
        if intent.intent_type == "verify":
            return self._compile_verify(intent)
        if intent.intent_type == "navigate":
            return self._compile_navigate(intent)
        if intent.intent_type == "expand":
            return self._compile_expand(intent)
        raise ValueError(f"Unknown intent: {intent.intent_type}")

    def _compile_find(self, intent: Intent) -> np.ndarray:
        """Feature map -> deterministic lattice address.

        An explicit ``anchor`` feature is lifted exactly. Otherwise the
        phi-weighted feature vector is rescaled by the monotone saturation
        ``r* = 89 * s / (1 + s)`` (``s`` = its golden norm), preserving
        direction while bounding the address to the lattice range.
        """
        features = intent.payload.get("features", {})
        if "anchor" in features:
            return anchor_to_vector(int(features["anchor"]))
        v = np.zeros(DIM, dtype=np.float64)
        for i, (_key, value) in enumerate(features.items()):
            if i >= DIM:
                break
            try:
                v[i] = float(value) * (PHI**-i)
            except (TypeError, ValueError):
                v[i] = float(abs(hash(str(value))) % 1000) / 1000.0 * (PHI**-i)
        s = weighted_norm(v)
        if s <= 0:
            return v
        radius = (ANCHOR_MODULUS - 1) * s / (1.0 + s)
        return v * (radius / s)

    def _compile_verify(self, intent: Intent) -> np.ndarray:
        anchor = int(intent.payload.get("anchor", 1))
        return anchor_to_vector(anchor)

    def _compile_navigate(self, intent: Intent) -> np.ndarray:
        target_anchor = int(intent.payload.get("target_anchor", 1))
        return anchor_to_vector(target_anchor)

    def _compile_expand(self, intent: Intent) -> np.ndarray:
        current_anchor = int(intent.payload.get("current_anchor", 1))
        return anchor_to_vector((current_anchor + 1) % ANCHOR_MODULUS)


__all__ = ["Intent", "IntentCompiler"]
