"""
EUCLID Cartesian Genetic Programming (CGP) Search Topology Controller
========================================================================
Manages CGP substrate grid parameters (n_cols, levels_back, pop_size) and
directly controls candidate population size, lookback depth, and mutation composition breadth.
"""

from typing import Dict, Any, Tuple

class CGPSearchTopologyController:
    """
    CGP Search Topology Controller.
    Dynamically dictates population breadth and composition depth based on substrate state.
    """
    def __init__(self, initial_n_cols: int = 12, initial_levels_back: int = 3, pop_size: int = 10):
        self.n_cols: int = initial_n_cols
        self.levels_back: int = initial_levels_back
        self.pop_size: int = pop_size
        self.total_expansions: int = 0
        self.total_contractions: int = 0
        self.stall_counter: int = 0

    def adapt_topology(self, generation_velocity: float) -> Tuple[bool, str]:
        """
        Adapts grid parameters based on fitness velocity.
        - High velocity (> 0.005) -> Expands search graph capacity (n_cols += 2, levels_back += 1)
        - Stall (0 velocity for 2+ generations) -> Reconfigures substrate to break local trap
        """
        if generation_velocity > 0.005:
            self.n_cols += 2
            self.levels_back += 1
            self.pop_size += 2
            self.total_expansions += 1
            self.stall_counter = 0
            return True, f"EXPANDED_SUBSTRATE: n_cols={self.n_cols}, levels_back={self.levels_back}, pop={self.pop_size}"
        
        elif abs(generation_velocity) < 1e-6:
            self.stall_counter += 1
            if self.stall_counter >= 2 and self.n_cols > 8:
                self.n_cols -= 1
                self.total_contractions += 1
                self.stall_counter = 0
                return True, f"STALL_RECONFIGURED: n_cols={self.n_cols}, levels_back={self.levels_back}"
        else:
            self.stall_counter = 0

        return False, "TOPOLOGY_UNCHANGED"

    def get_candidate_population_size(self) -> int:
        """Returns candidate population size dictated by topology."""
        return self.pop_size

    def allow_composite_mutations(self) -> bool:
        """Determines if substrate width allows multi-step composite mutations."""
        return self.n_cols >= 14

    def get_lookback_depth(self) -> int:
        """Returns lookback depth for AST subtree refactoring."""
        return self.levels_back

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cols": self.n_cols,
            "levels_back": self.levels_back,
            "pop_size": self.pop_size,
            "total_expansions": self.total_expansions,
            "total_contractions": self.total_contractions,
            "allow_composite_mutations": self.allow_composite_mutations()
        }

# Alias for backward compatibility
CGPGeometryState = CGPSearchTopologyController
