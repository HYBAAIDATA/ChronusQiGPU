"""Neuromorphic hybrid model (Loihi 2 / SpiNNaker)."""
from dataclasses import dataclass
from typing import Dict


@dataclass
class NeuromorphicHybrid:
    """Model of a neuromorphic co-processor paired with the φ-substrate."""
    target: str = "Intel Loihi 2"
    neurons: int = 1_000_000
    synapses: int = 120_000_000
    power_mw: float = 100.0

    def synaptic_ops_per_second(self, spike_rate_hz: float = 100.0) -> Dict:
        return {
            "target": self.target,
            "neurons": self.neurons,
            "synapses": self.synapses,
            "synops_per_second": self.synapses * spike_rate_hz,
            "claim_lane": "RESTRICTED — model; no hardware benchmark",
        }
