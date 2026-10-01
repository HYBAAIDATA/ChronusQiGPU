"""Adaptive search geometry for the production PYTHAGORAS evolution engine.

``n_cols`` is the number of ranked operators evaluated per generation.
``levels_back`` is the maximum composite-recipe length. No DAG population is
represented or evolved; ``pop_size`` remains constructor-only compatibility input.
"""

from typing import Any, Dict, List, Optional, Tuple


class CGPGeometryState:
    """Measured, bounded search-breadth and recipe-depth state."""

    def __init__(
        self,
        initial_n_cols: int = 12,
        initial_levels_back: int = 3,
        pop_size: int = 10,
    ):
        self.n_cols = initial_n_cols
        self.levels_back = initial_levels_back
        _ = pop_size
        self.total_expansions = 0
        self.total_contractions = 0
        self.stall_counter = 0

    def adapt(self, generation_velocity: float) -> Tuple[bool, str]:
        if generation_velocity > 0.005:
            self.n_cols += 2
            self.levels_back += 1
            self.total_expansions += 1
            self.stall_counter = 0
            return True, f"EXPANDED: n_cols={self.n_cols}, levels_back={self.levels_back}"

        if abs(generation_velocity) < 1e-6:
            self.stall_counter += 1
            if self.stall_counter >= 2 and self.n_cols > 8:
                self.n_cols -= 1
                self.total_contractions += 1
                self.stall_counter = 0
                return True, (
                    f"STALL_RECONFIGURED: n_cols={self.n_cols}, "
                    f"levels_back={self.levels_back}"
                )
        else:
            self.stall_counter = 0

        return False, "UNCHANGED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cols": self.n_cols,
            "levels_back": self.levels_back,
            "total_expansions": self.total_expansions,
            "total_contractions": self.total_contractions,
        }

    @classmethod
    def from_dict(cls, state: Optional[Dict[str, Any]] = None) -> "CGPGeometryState":
        state = state or {}
        obj = cls(
            initial_n_cols=int(state.get("n_cols", 12)),
            initial_levels_back=int(state.get("levels_back", 3)),
        )
        obj.total_expansions = int(state.get("total_expansions", 0))
        obj.total_contractions = int(state.get("total_contractions", 0))
        return obj


class CollectiveGeometryCoordinator:
    """Share bounded geometry knowledge across files and persisted sessions."""

    def __init__(self, state: Optional[Dict[str, Any]] = None):
        state = state or {}
        self.observations: List[Dict[str, Any]] = list(state.get("observations", []))[-100:]

    def initial_state(self) -> CGPGeometryState:
        if not self.observations:
            return CGPGeometryState()
        cols = sorted(int(item["n_cols"]) for item in self.observations)
        levels = sorted(int(item["levels_back"]) for item in self.observations)
        mid = len(cols) // 2
        return CGPGeometryState(
            initial_n_cols=max(8, min(32, cols[mid])),
            initial_levels_back=max(2, min(8, levels[mid])),
        )

    def observe(self, target: str, geometry: CGPGeometryState, delta_phi: float) -> None:
        self.observations.append(
            {
                "target": target,
                "n_cols": geometry.n_cols,
                "levels_back": geometry.levels_back,
                "delta_phi": round(float(delta_phi), 6),
            }
        )
        self.observations = self.observations[-100:]

    def to_dict(self) -> Dict[str, Any]:
        return {"observations": list(self.observations)}
