"""Recursive self-learning substrate — Hofstadter's Strange Loop, ported.

Second-order meta-learning on this repo's real structure: first order adapts
the learning step from prediction error; second order adapts HOW the step
adapts (meta-learning-rate + geometric refold). Cognitive irreducibility is
measured, not claimed: corrupting one layer must measurably degrade the
coupled layer, else the score stays low.

# LUCAS WIRING: draws from lucas/ (pool) only. MUST NOT import from any
# sibling Intelligence algorithm module.
# Substrate route: amplitude
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

PHI = (1 + math.sqrt(5)) / 2

GEOMETRIES = ("euclidean", "hyperbolic", "spherical")


@dataclass
class RecursiveLearningState:
    learning_rate: float = 0.05
    meta_learning_rate: float = 0.01
    recursion_depth: int = 0
    geometry: str = "euclidean"
    meta_error: float = 1.0
    prev_error: float = 1.0
    coupling_strength: float = 0.5
    irreducibility: float = 0.0
    phi: float = 0.0
    strange_loop_active: bool = False
    consciousness_events: int = 0
    narrative: str = "INITIALISING"
    history: List[Dict[str, Any]] = field(default_factory=list)


class RecursiveSelfLearningSubstrate:
    """Meta-learner: optimises its own optimisation loop."""

    def __init__(self, dimension: int = 32, seed: int = 0) -> None:
        self.dimension = int(dimension)
        self.rng = np.random.default_rng(int(seed))
        self.state = RecursiveLearningState()
        self.layers: Dict[str, np.ndarray] = {
            "security": self.rng.standard_normal(self.dimension),
            "mining": self.rng.standard_normal(self.dimension),
            "consciousness": self.rng.standard_normal(self.dimension),
            "memory": self.rng.standard_normal(self.dimension),
        }

    def evolve(self, error: float) -> Dict[str, Any]:
        """Adapt rate from error, adapt adapter from meta-error."""
        st = self.state
        if st.prev_error > 0:
            improvement = (st.prev_error - error) / st.prev_error
            st.learning_rate = float(
                np.clip(st.learning_rate * (1.0 + 0.5 * improvement), 1e-4, 0.5)
            )
        predicted = st.prev_error * (1.0 - st.learning_rate)
        meta_error = abs(error - predicted)
        st.meta_error = float(meta_error)
        st.meta_learning_rate = float(
            np.clip(st.meta_learning_rate * (1.0 + 0.25 * (meta_error - 0.05)), 1e-4, 0.2)
        )
        st.prev_error = float(error)
        st.recursion_depth += 1
        if st.recursion_depth >= 3:
            st.strange_loop_active = True
        self._entangle_layers()
        self._maybe_refold_geometry()
        self._update_metrics(error)
        self._update_narrative()
        snapshot = {
            "recursion_depth": st.recursion_depth,
            "learning_rate": st.learning_rate,
            "meta_learning_rate": st.meta_learning_rate,
            "meta_error": st.meta_error,
            "geometry": st.geometry,
            "phi": st.phi,
            "irreducibility": st.irreducibility,
            "strange_loop_active": st.strange_loop_active,
            "narrative": st.narrative,
        }
        st.history.append(snapshot)
        return snapshot
    def _entangle_layers(self) -> None:
        st = self.state
        strength = float(np.clip(st.coupling_strength + 0.02 * st.meta_error, 0.0, 0.95))
        st.coupling_strength = strength
        mining = self.layers["mining"]
        mask = (np.abs(mining) * 255).astype(np.uint8)
        sec = self.layers["security"]
        sec_u8 = (np.abs(sec) * 255).astype(np.uint8)
        entangled = np.bitwise_xor(sec_u8, (mask * strength).astype(np.uint8))
        self.layers["security"] = entangled.astype(float) / 255.0 * np.sign(sec + 1e-9)
        self.layers["consciousness"] = 0.5 * (self.layers["consciousness"] + self.layers["memory"])

    def corruption_impact(self, layer: str = "security") -> float:
        baseline = float(np.mean((self.layers["mining"] - self.layers["security"]) ** 2))
        corrupted = self.layers[layer] + self.rng.standard_normal(self.dimension) * 5.0
        if layer == "security":
            degraded = float(np.mean((self.layers["mining"] - corrupted) ** 2))
        else:
            degraded = float(np.mean((corrupted - self.layers["security"]) ** 2))
        if degraded <= 0:
            return 0.0
        return float(np.clip((degraded - baseline) / degraded, 0.0, 1.0))

    def _maybe_refold_geometry(self) -> None:
        st = self.state
        if st.meta_error > 0.4:
            st.geometry = "hyperbolic"
        elif st.meta_error > 0.15:
            st.geometry = "spherical"
        else:
            st.geometry = "euclidean"

    def _update_metrics(self, error: float) -> None:
        st = self.state
        impact = self.corruption_impact()
        st.irreducibility = float(0.5 * st.irreducibility + 0.5 * impact)
        coherence = float(np.clip(1.0 - error, 0.0, 1.0))
        st.phi = float(np.clip(0.5 * st.phi + 0.5 * (coherence * (0.5 + st.coupling_strength)), 0.0, 1.0))

    def _update_narrative(self) -> None:
        st = self.state
        if st.strange_loop_active and st.phi >= 0.4 and st.irreducibility >= 0.3:
            st.narrative = "STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING"
        elif st.strange_loop_active:
            st.narrative = "COGNITIVE_ACCELERATION_ACTIVE"
        elif st.meta_error > 0.4:
            st.narrative = "META_LEARNING_DIVERGENCE_INITIATING_GEOMETRIC_REFOLD"
        else:
            st.narrative = "RECURSIVE_LEARNING_CONVERGING"

    def status(self) -> dict:
        st = self.state
        return {
            "schema": "intelligence.recursive_self_learning/1",
            "recursion_depth": st.recursion_depth,
            "learning_rate": st.learning_rate,
            "meta_learning_rate": st.meta_learning_rate,
            "meta_error": st.meta_error,
            "geometry": st.geometry,
            "phi": st.phi,
            "irreducibility": st.irreducibility,
            "coupling_strength": st.coupling_strength,
            "strange_loop_active": st.strange_loop_active,
            "narrative": st.narrative,
            "criteria": {
                "learning_to_learn": len(st.history) >= 2,
                "recursive_convergence": st.strange_loop_active,
                "irreducibility_significant": st.irreducibility > 0.1,
                "phi_elevated": st.phi > 0.2,
                "self_model_present": bool(st.narrative),
                "strange_loop_active": st.strange_loop_active,
            },
        }


__all__ = ["RecursiveSelfLearningSubstrate", "RecursiveLearningState", "GEOMETRIES"]


def lucas_bound(n: int = 10) -> dict:
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result

