"""Plasticity wiring over Apple Silicon subsystems.

Co-activation of ANE / Metal / Accelerate subsystems during workloads;
reward reflects workload success. Off macOS the subsystems report
available=False — the plasticity graph still exercises honestly.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: trace
"""

from __future__ import annotations

from .neural_plasticity import NeuralPlasticity
from .apple_features import AppleSiliconRuntime
from Intelligence._born import born_evidence


class ApplePlasticity:
    """Neural plasticity wired to Apple Silicon subsystems."""

    def __init__(self):
        self.apple = AppleSiliconRuntime()
        self.plasticity = NeuralPlasticity(
            learning_rate=0.06,
            trace_decay=0.88,
            weight_decay=0.015,
            sprout_threshold=2,
            prune_threshold=0.015,
            crystallize_threshold=0.82,
        )
        for name in [
            "ane_coreml",
            "ane_compile",
            "metal_kernel",
            "metal_buffers",
            "accelerate_blas",
            "accelerate_fft",
            "accelerate_vforce",
            "unified_memory",
            "zero_copy",
        ]:
            self.plasticity.register_subsystem(name)

    # workload -> measured hardware flags its reward is evidence of
    _WORKLOAD_FLAGS = {
        "ane_inference": ("neural_engine",),
        "metal_compute": ("metal",),
        "accelerate_blas": ("accelerate",),
    }

    def _measured_reward(self, workload: str) -> float:
        """Born evidence over the workload's real hardware availability.

        0.95/0.90/0.85 magic rewards are gone: the reward is the measured
        posterior that the workload's subsystems are actually available
        (flat 0.5 prior for unmapped workloads).
        """
        runtime = self.apple
        flags = {
            "neural_engine": bool(getattr(runtime.neural_engine, "available", False)),
            "metal": bool(getattr(runtime.metal, "available", False)),
            "accelerate": bool(getattr(runtime.accelerate, "available", False)),
        }
        wanted = self._WORKLOAD_FLAGS.get(workload)
        if not wanted:
            return born_evidence(0, 0)  # flat prior — unmeasured workload
        available = sum(1 for f in wanted if flags[f])
        return born_evidence(available, len(wanted) - available)

    def execute_apple_workload(self, workload: str) -> dict:
        if workload == "ane_inference":
            self.plasticity.co_activate("ane_coreml", "unified_memory")
            self.plasticity.co_activate("ane_coreml", "zero_copy")
        elif workload == "metal_compute":
            self.plasticity.co_activate("metal_kernel", "unified_memory")
            self.plasticity.co_activate("metal_kernel", "zero_copy")
        elif workload == "accelerate_blas":
            self.plasticity.co_activate("accelerate_blas", "unified_memory")
        reward = self._measured_reward(workload)
        self.plasticity.deliver_reward(reward)
        self.plasticity.decay()
        self.plasticity.prune()
        self.plasticity.crystallize()
        return {
            "workload": workload,
            "reward": reward,
            "report": self.plasticity.report(),
        }

    def telemetry(self) -> dict:
        return {
            "apple": self.apple.telemetry(),
            "plasticity": self.plasticity.report(),
        }
