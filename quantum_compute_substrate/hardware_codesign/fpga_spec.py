"""FPGA kernel specification for the φ-fold operator."""
from dataclasses import dataclass
from typing import Dict


@dataclass
class FPGAKernelSpec:
    """Architecture spec for an FPGA implementation of φ-fold."""
    target_device: str = "Xilinx Alveo U280"
    logic_cells: int = 1_100_000
    dsp48_blocks: int = 9024
    hbm_capacity_gb: float = 8.0
    hbm_bandwidth_gbs: float = 460.0
    target_clock_mhz: float = 300.0

    def kernel_resource_estimate(self, dim: int, precision_bits: int = 32) -> Dict:
        """Estimate FPGA resources for a φ-fold kernel of given state dim."""
        # Rough estimate: complex mult = 4 real mults + 2 adds -> 4 DSPs
        complex_mults_per_iter = 3 * dim
        dsps_required = complex_mults_per_iter * 4 // 100  # pipelined /100
        bram_kb = dim * precision_bits * 2 / 1024 / 8  # complex
        latency_cycles = dim + 20  # pipeline depth
        return {
            "target": self.target_device,
            "dim": dim,
            "dsps_estimated": dsps_required,
            "dsps_available": self.dsp48_blocks,
            "bram_kb_estimated": bram_kb,
            "latency_cycles": latency_cycles,
            "latency_us": latency_cycles / self.target_clock_mhz,
            "feasible": dsps_required <= self.dsp48_blocks,
            "claim_lane": "RESTRICTED — architecture estimate only; no place/route",
        }
