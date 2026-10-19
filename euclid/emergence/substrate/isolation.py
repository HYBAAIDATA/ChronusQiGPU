"""Substrate independence verification and isolation criteria."""

from __future__ import annotations
from typing import Optional, Tuple, List, Any
from ..models.substrate import SubstrateProperties


class SubstrateIndependenceVerifier:
    """Verifies that two executors/substrates are truly independent without cross-contamination."""

    @staticmethod
    def verify_isolation(
        prop_a: SubstrateProperties,
        prop_b: SubstrateProperties,
        exec_a: Optional[Any] = None,
        exec_b: Optional[Any] = None,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []

        if prop_a.compute_id() == prop_b.compute_id():
            violations.append("Identical substrate configuration: cross-substrate reproduction requires distinct substrates.")

        if prop_a.sandbox_id and prop_b.sandbox_id and prop_a.sandbox_id == prop_b.sandbox_id:
            violations.append(f"Shared sandbox instance detected: '{prop_a.sandbox_id}'")

        if exec_a is not None and exec_b is not None:
            if exec_a is exec_b:
                violations.append("Executor instances are identical objects in memory.")

            state_a = getattr(exec_a, "state_store", None)
            state_b = getattr(exec_b, "state_store", None)
            if state_a is not None and state_b is not None and state_a is state_b:
                violations.append("Executors share the same state store memory reference.")

        operational_differences = 0
        if prop_a.executor_type != prop_b.executor_type:
            operational_differences += 1
        if prop_a.compute_substrate != prop_b.compute_substrate:
            operational_differences += 1
        if abs(prop_a.observation_latency - prop_b.observation_latency) > 0.001:
            operational_differences += 1
        if prop_a.action_granularity != prop_b.action_granularity:
            operational_differences += 1

        if operational_differences == 0:
            violations.append("Substrates lack divergence in executor type, latency, compute substrate, or action granularity.")

        is_independent = len(violations) == 0
        return is_independent, violations
