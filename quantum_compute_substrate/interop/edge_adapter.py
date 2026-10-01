"""Edge / IoT deployment configuration."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EdgeDeployment:
    """Configuration for an edge deployment."""

    target: str = "NVIDIA Jetson Orin Nano"
    memory_gb: float = 8.0
    max_state_dim: int = 4096
    precision: str = "fp16"
    features: List[str] = field(
        default_factory=lambda: [
            "tensor_core",
            "quantum_kernel",
            "grover_search",
            "vqe_h2",
        ]
    )

    def status(self) -> Dict:
        return {
            "target": self.target,
            "memory_gb": self.memory_gb,
            "max_state_dim": self.max_state_dim,
            "precision": self.precision,
            "features": self.features,
        }
