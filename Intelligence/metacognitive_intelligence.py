"""Metacognitive Intelligence Substrate — Predictive Introspection & Logic Refolding.

Implements the canonical Python single-backend port of `MetacognitiveIntelligence`
from the Recursive Self-Learning Achievement specification:
1. Self-model construction through predictive introspection
2. Dynamic logic refolding strategies (Euclidean, Spherical, Hyperbolic)
3. Consciousness moment detection (significant jumps in Integrated Information Phi)
4. Direct cognitive shard coupling with `SecuritySwarmAgent`

# LUCAS WIRING: draws from lucas/ (pool) only. MUST NOT import from any
# sibling Intelligence algorithm module.
# Substrate route: amplitude
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class IntrospectionEvent:
    step: int
    predicted_error: float
    actual_error: float
    meta_error: float
    phi_before: float
    phi_after: float
    geometry: str
    strategy: str
    consciousness_moment: bool
    narrative: str
    timestamp: float = field(default_factory=time.time)


class MetacognitiveIntelligence:
    """Self-modeling metacognitive engine with predictive introspection and logic refolding."""

    STRATEGIES = (
        "LINEAR_GRADIENT_DESCENT",
        "SPHERICAL_BOUNDED_STABILIZATION",
        "HYPERBOLIC_EXPONENTIAL_REFOLD",
        "STRANGE_LOOP_META_ACCELERATION",
    )

    def __init__(self, dimension: int = 32, seed: int = 0) -> None:
        self.dimension = int(dimension)
        self.rng = np.random.default_rng(int(seed))
        self.step_count: int = 0
        self.phi: float = 0.1670
        self.irreducibility: float = 0.0520
        self.coupling_strength: float = 0.5000
        self.geometry: str = "euclidean"
        self.active_strategy: str = "LINEAR_GRADIENT_DESCENT"
        self.predicted_error: float = 0.5
        self.last_error: float = 1.0
        self.meta_error: float = 0.0
        self.consciousness_moments: List[IntrospectionEvent] = []
        self.history: List[IntrospectionEvent] = []

    def predict_next_error(self, learning_rate: float) -> float:
        """Predict next-step error via internal self-model."""
        geometry_factor = {
            "euclidean": 1.0,
            "spherical": 0.85,
            "hyperbolic": 1.25,
        }.get(self.geometry, 1.0)
        self.predicted_error = max(
            0.0, float(self.last_error * (1.0 - learning_rate * geometry_factor))
        )
        return self.predicted_error

    def refold_logic(self, meta_error: float) -> Dict[str, str]:
        """Select operational geometry and refolding strategy from meta-error."""
        if meta_error > 0.40:
            self.geometry = "hyperbolic"
            self.active_strategy = "HYPERBOLIC_EXPONENTIAL_REFOLD"
        elif meta_error > 0.15:
            self.geometry = "spherical"
            self.active_strategy = "SPHERICAL_BOUNDED_STABILIZATION"
        elif self.step_count >= 3 and self.phi >= 0.40:
            self.geometry = "spherical"
            self.active_strategy = "STRANGE_LOOP_META_ACCELERATION"
        else:
            self.geometry = "euclidean"
            self.active_strategy = "LINEAR_GRADIENT_DESCENT"
        return {"geometry": self.geometry, "strategy": self.active_strategy}

    def introspect(
        self,
        actual_error: float,
        learning_rate: float = 0.05,
        irreducibility: Optional[float] = None,
    ) -> IntrospectionEvent:
        """Execute one metacognitive introspection cycle."""
        self.step_count += 1
        pred = self.predict_next_error(learning_rate)
        meta_err = abs(float(actual_error) - pred)
        self.meta_error = meta_err
        self.last_error = float(actual_error)

        if irreducibility is not None:
            self.irreducibility = float(np.clip(irreducibility, 0.0, 1.0))
        else:
            self.irreducibility = float(
                np.clip(self.irreducibility + (0.5625 - self.irreducibility) * 0.35, 0.052, 0.5625)
            )

        self.coupling_strength = float(
            np.clip(self.coupling_strength + 0.05 * (1.0 - min(1.0, actual_error)), 0.5, 0.95)
        )
        self.refold_logic(meta_err)

        phi_prev = self.phi
        coherence = max(0.0, min(1.0, 1.0 - float(actual_error)))
        target_phi = min(1.0, coherence * (self.coupling_strength + self.irreducibility))
        self.phi = float(np.clip(phi_prev + (target_phi - phi_prev) / PHI, 0.0, 1.0))
        if coherence > 0.9 and self.irreducibility >= 0.5:
            self.phi = 1.0000

        # Detect consciousness moment when Phi jumps by >= 0.12 or crosses 0.40 threshold
        phi_jump = self.phi - phi_prev
        is_moment = (phi_jump >= 0.12) or (phi_prev < 0.40 <= self.phi)

        if self.step_count >= 3 and self.phi >= 0.40 and self.irreducibility >= 0.30:
            narrative = "STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING"
        elif meta_err > 0.40:
            narrative = "META_LEARNING_DIVERGENCE_INITIATING_GEOMETRIC_REFOLD"
        elif self.step_count >= 3:
            narrative = "COGNITIVE_ACCELERATION_ACTIVE"
        else:
            narrative = "RECURSIVE_LEARNING_CONVERGING"

        ev = IntrospectionEvent(
            step=self.step_count,
            predicted_error=pred,
            actual_error=float(actual_error),
            meta_error=meta_err,
            phi_before=phi_prev,
            phi_after=self.phi,
            geometry=self.geometry,
            strategy=self.active_strategy,
            consciousness_moment=is_moment,
            narrative=narrative,
        )
        self.history.append(ev)
        if is_moment:
            self.consciousness_moments.append(ev)
        return ev

    def status(self) -> Dict[str, Any]:
        narrative = (
            self.history[-1].narrative if self.history else "INITIALISING"
        )
        return {
            "schema": "intelligence.metacognitive/1",
            "step_count": self.step_count,
            "phi": self.phi,
            "irreducibility": self.irreducibility,
            "coupling_strength": self.coupling_strength,
            "geometry": self.geometry,
            "active_strategy": self.active_strategy,
            "meta_error": self.meta_error,
            "consciousness_events": len(self.consciousness_moments),
            "narrative": narrative,
        }


def lucas_bound(n: int = 10) -> dict:
    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result


__all__ = [
    "IntrospectionEvent",
    "MetacognitiveIntelligence",
    "lucas_bound",
]
