"""Classical Adaptive Tensor Contraction Pathway with Pathway Optimization.

Renamed per Consortium Charter:
- 'superposition' -> parallel_pathway_search
- 'interference' -> weighted_pathway_aggregation
- 'quantum-inspired' -> classical_tensor_network
- Latency is measured at runtime (perf_counter_ns), not claimed.
- All outputs explicitly state is_quantum = False.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from chronus.tensor.enhanced_representation import (
    ContractionTree,
    EnhancedTensorRepresentation,
    search_contraction_trees,
    select_best_tree,
    execute_sharded_contraction,
)


class AdaptiveTensorContractionPathway:
    """Adaptive Tensor Contraction Pathway using Classical Search and Ranking.

    Evaluates candidate contraction trees using classical multi-path search
    and weighted cost ranking.
    """

    def __init__(
        self,
        tensor_network: EnhancedTensorRepresentation,
        optimization_level: int = 3,
    ) -> None:
        self.tensor_network = tensor_network
        self.optimization_level = optimization_level
        self.dimensions = tensor_network.dimensions
        self.site_dim = tensor_network.site_dim
        self.bond_dim = tensor_network.bond_dim

    def parallel_pathway_search(
        self, query_payload: Dict[str, Any]
    ) -> List[ContractionTree]:
        """Classical parallel evaluation of candidate contraction trees (formerly 'superposition')."""
        return search_contraction_trees(
            self.tensor_network.network,
            budget=self.tensor_network.cfg.planner_budget_bytes,
        )

    def weighted_pathway_aggregation(
        self,
        candidates: List[ContractionTree],
        query_payload: Dict[str, Any],
    ) -> Tuple[ContractionTree, List[ContractionTree]]:
        """Cost-based selection of optimal contraction tree (formerly 'interference')."""
        best = select_best_tree(
            candidates,
            budget=self.tensor_network.cfg.planner_budget_bytes,
        )
        return best, candidates

    def optimize_contraction(self, query_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run actual CPU MPS contraction; never assert GPU work without backend."""
        if query_payload not in ({}, {"operation": "norm"}):
            raise NotImplementedError("adaptive contraction objective unavailable")
        start = time.perf_counter_ns()
        candidates = self.parallel_pathway_search(query_payload)
        best, all_trees = self.weighted_pathway_aggregation(candidates, query_payload)
        result = execute_sharded_contraction(
            self.tensor_network.shard_plan, best, self.tensor_network.network)
        return {
            **result, "optimal_route": best.name, "strategy": best.strategy,
            "latency_ms": round((time.perf_counter_ns()-start)/1e6, 4),
            "parallel_candidates_evaluated": len(all_trees),
            "optimization_level": self.optimization_level,
            "method": "finite_precision_mps_norm_transfer",
            "refused_claims": ["0.01ms latency", "708x speedup", "100X information density"],
        }
