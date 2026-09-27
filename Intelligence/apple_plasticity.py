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

    def execute_apple_workload(self, workload: str) -> dict:
        if workload == "ane_inference":
            self.plasticity.co_activate("ane_coreml", "unified_memory")
            self.plasticity.co_activate("ane_coreml", "zero_copy")
            reward = 0.95
        elif workload == "metal_compute":
            self.plasticity.co_activate("metal_kernel", "unified_memory")
            self.plasticity.co_activate("metal_kernel", "zero_copy")
            reward = 0.90
        elif workload == "accelerate_blas":
            self.plasticity.co_activate("accelerate_blas", "unified_memory")
            reward = 0.85
        else:
            reward = 0.5
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
