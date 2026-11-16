"""Application facade for exact TURING mathematics and optional Metal compute.

This API deliberately refuses to label any float32 MLX matrix product an
exact exp(-iHt). Exact evolution is supported for Hermitian involutions
under TURING ownership. Metal accelerates an explicitly approximate
32x600 dual-Laplacian linear operation when an Apple GPU is available.
"""
from __future__ import annotations

from typing import Any, Collection, Mapping

from chronus.compute.igpu_dispatcher import ComputeTask, iGPUDispatcher


class iGPUQuantumEvolution:
    """Lifecycle-owned mathematical compute coordinator.

    No mining/pool integration, global accelerator side effect or
    automatic reference downgrade is performed by this component.
    """

    def __init__(self, dispatcher: iGPUDispatcher | None = None) -> None:
        self.dispatcher = dispatcher or iGPUDispatcher()
        self._counter = 0
        self.dispatcher.start()

    def _call(self, operation: str, data: dict[str, Any],
              timeout: float | None = 60) -> dict[str, Any]:
        self._counter += 1
        task = ComputeTask(
            task_id=f"chronus-cal-{self._counter}",
            operation=operation, data=data,
        )
        return self.dispatcher.submit_sync(task, timeout=timeout)

    def evolve_exact(self, state: object, operator: object,
                     quarter_turns: int = 1) -> dict[str, Any]:
        """TURING exact unitary for Hermitian involutions, host classification."""
        return self._call(
            "exact-involution",
            {"state": state, "operator": operator,
             "quarter_turns": quarter_turns},
        )

    def phase_exact(self, state: object,
                    phases: Mapping[int, object]) -> dict[str, Any]:
        """TURING exact diagonal unit-phase operation."""
        return self._call(
            "exact-phase", {"state": state, "phases": dict(phases)},
        )

    def amplify_exact(self, state: object, reference: object,
                      marked: Collection[int]) -> dict[str, Any]:
        """TURING oracle/reflection for supplied marked set; query cost external."""
        return self._call(
            "exact-amplify",
            {"state": state, "reference": reference, "marked": tuple(marked)},
        )

    def laplacian_exact(self, integral_state: object) -> dict[str, Any]:
        """Exact I32 tensor L_120CELL applied to 32x600 integer stalks."""
        return self._call("exact-dual-laplacian", {"state": integral_state})

    def laplacian_metal(self, float32_state: object) -> dict[str, Any]:
        """Actual MLX GPU float32 I32 tensor L_120CELL with host parity.

        Raises on unsupported host/device. Does not perform physical
        quantum evolution and never silently uses the CPU reference.
        """
        return self._call("metal-dual-laplacian", {"state": float32_state})

    def matmul_metal(self, left: object, right: object) -> dict[str, Any]:
        """Bounded, explicitly approximate GPU matrix product."""
        return self._call("metal-matmul", {"left": left, "right": right})

    @staticmethod
    def inspect_probabilities(state: object) -> dict[int, object]:
        from turing.exact.geometry.hilbert import SparseState
        if not isinstance(state, SparseState):
            raise TypeError("requires a TURING exact finite Hilbert state")
        return state.born_distribution()

    def performance_report(self) -> dict[str, Any]:
        """Only completed task observations; no asserted device throughput."""
        return {
            "classifications": [
                "MATHEMATICAL_EXECUTION_HOST",
                "METAL_APPROXIMATE_FLOAT32",
            ],
            "stats": self.dispatcher.get_stats(),
            "memory": self.dispatcher.memory_usage(),
            "physical_device_attested": False,
        }

    def shutdown(self) -> None:
        self.dispatcher.stop()
