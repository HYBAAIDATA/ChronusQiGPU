"""Deterministic routing into PULVINI for large workloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

from ..operators.matrix_product_operator import MatrixProductOperator, MPOPulviniTTHybrid


@dataclass(frozen=True)
class RoutingPlan:
    mode: str
    shape: Tuple[int, ...]
    element_count: int
    threshold: int
    reason: str


class QuantumTopologyOrchestrator:
    """Route large tensor workloads without silently materialising huge matrices."""

    def __init__(self, large_dimension_threshold: int = 10_000, tolerance: float = 1e-5):
        if large_dimension_threshold < 1:
            raise ValueError("large_dimension_threshold must be positive")
        self.large_dimension_threshold = int(large_dimension_threshold)
        self.tolerance = float(tolerance)

    def plan(self, shape: Tuple[int, ...]) -> RoutingPlan:
        normalized = tuple(int(x) for x in shape)
        if not normalized or any(x < 1 for x in normalized):
            raise ValueError("shape must contain positive dimensions")
        count = int(np.prod(normalized, dtype=np.int64))
        large = count > self.large_dimension_threshold
        return RoutingPlan(
            mode="pulvini_tt_mpo" if large else "direct",
            shape=normalized,
            element_count=count,
            threshold=self.large_dimension_threshold,
            reason="element_count_exceeds_threshold" if large else "element_count_within_threshold",
        )

    def process(
        self,
        tensor: np.ndarray,
        mpo: Optional[MatrixProductOperator] = None,
        num_time_steps: int = 1,
    ) -> dict[str, Any]:
        value = np.asarray(tensor)
        route = self.plan(value.shape)
        if route.mode == "direct":
            return {"route": route, "state": value.copy(), "processed": False}
        engine = MPOPulviniTTHybrid(tolerance=self.tolerance)
        result = engine.process(value, mpo=mpo, num_time_steps=num_time_steps)
        result["route"] = route
        result["processed"] = True
        return result
