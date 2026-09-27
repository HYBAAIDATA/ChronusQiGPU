"""
PYTHAGORAS — GEOMETRY EVOLUTION
Modifies CGP substrate parameters in response to fitness landscape curvature.

Features:
- Substrate geometry vector: n_cols, levels_back, pop_size
- ENH-06: Geometry trigger decoupling — binds expansion to curvature d²φ/dt²
  and surrogate velocity v_surrogate
- ENH-07: Levels-back evolution — adds dynamic depth adaptation to substrate plasticity
- ENH-14: Collective geometry — multi-file substrate consensus for codebase-level intelligence
"""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np


class GeometryEvolution:
    """
    Deepest adaptation layer.
    Modifies the structural parameters of the Cartesian Genetic Programming substrate:
    - n_cols: Horizontal width of DAG
    - levels_back: Maximum distance backwards that nodes can connect (ENH-07)
    - pop_size: Evolutionary population size
    """

    def __init__(
        self,
        n_cols: int = 12,
        levels_back: int = 3,
        pop_size: int = 50,
        min_cols: int = 6,
        max_cols: int = 32,
        min_levels_back: int = 2,
        max_levels_back: int = 10,
        min_pop_size: int = 20,
        max_pop_size: int = 200,
    ):
        self.n_cols = max(min_cols, int(n_cols))
        self.levels_back = max(min_levels_back, int(levels_back))
        self.pop_size = max(min_pop_size, int(pop_size))

        self.min_cols = min_cols
        self.max_cols = max_cols
        self.min_levels_back = min_levels_back
        self.max_levels_back = max_levels_back
        self.min_pop_size = min_pop_size
        self.max_pop_size = max_pop_size

        self.history: List[Dict[str, Any]] = []

    def evolve(
        self,
        fitness_history: List[float],
        surrogate_velocity: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Evolve CGP substrate parameters based on fitness landscape curvature
        and surrogate velocity (ENH-06 Trigger Decoupling).
        """
        curvature = self._compute_curvature(fitness_history)
        action = "steady"

        # Expansion trigger: positive curvature AND positive surrogate velocity
        if curvature > 0.01 and surrogate_velocity > 0.05:
            self.n_cols = min(self.max_cols, self.n_cols + 2)
            self.levels_back = min(self.max_levels_back, self.levels_back + 1)
            self.pop_size = min(self.max_pop_size, self.pop_size + 10)
            action = "expand"

        # Contraction trigger: negative curvature indicating stalled gradient
        elif curvature < -0.01:
            self.n_cols = max(self.min_cols, self.n_cols - 1)
            self.levels_back = max(self.min_levels_back, self.levels_back - 1)
            self.pop_size = max(self.min_pop_size, self.pop_size - 5)
            action = "contract"

        record = {
            "n_cols": self.n_cols,
            "levels_back": self.levels_back,
            "pop_size": self.pop_size,
            "curvature": curvature,
            "surrogate_velocity": surrogate_velocity,
            "action": action,
        }
        self.history.append(record)
        return record

    def _compute_curvature(self, fitness_history: List[float]) -> float:
        """
        Compute discrete second derivative (curvature) of fitness trajectory:
        curvature = (φ_t - φ_{t-1}) - (φ_{t-1} - φ_{t-2}).
        """
        if len(fitness_history) < 3:
            return 0.0

        d1 = fitness_history[-1] - fitness_history[-2]
        d2 = fitness_history[-2] - fitness_history[-3]
        return float(d1 - d2)

    def get_state(self) -> Dict[str, Any]:
        """Return snapshot of current geometry parameters."""
        return {
            "n_cols": self.n_cols,
            "levels_back": self.levels_back,
            "pop_size": self.pop_size,
        }

    @staticmethod
    def compute_consensus(file_geometries: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        ENH-14: Collective geometry consensus.
        Aggregates geometry adaptation records across multiple files
        to determine the codebase-level equilibrium substrate.
        """
        if not file_geometries:
            return {"n_cols": 12, "levels_back": 3, "pop_size": 50}

        cols = [g.get("n_cols", 12) for g in file_geometries]
        levels = [g.get("levels_back", 3) for g in file_geometries]
        pops = [g.get("pop_size", 50) for g in file_geometries]

        consensus = {
            "n_cols": int(round(float(np.median(cols)))),
            "levels_back": int(round(float(np.median(levels)))),
            "pop_size": int(round(float(np.median(pops)))),
        }
        return consensus
