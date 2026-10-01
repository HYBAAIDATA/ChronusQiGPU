"""Quantum metrology at the Heisenberg limit.

GHZ state |GHZ_N> gives QFI = N^2 for phase encoding U = exp(-i theta sum_j Z_j),
saturating the Heisenberg limit. Product state gives QFI = N (standard quantum
limit). These are hard, exact facts.
"""

from __future__ import annotations
import numpy as np
from typing import Dict


def ghz_qfi(num_qubits: int) -> float:
    """Heisenberg-limit QFI for GHZ state with generator sum_j Z_j / 2.

    Generator G = sum_j Z_j; on |GHZ_N> = (|0..0> + |1..1>)/sqrt(2):
      <G> = 0, <G^2> = N^2 (since (sum Z_j)|0..0> = N|0..0> and = -N|1..1>).
    QFI = 4 * Var(G) = 4 * N^2. We report the standard convention QFI = N^2 by
    absorbing the 1/2 into the generator.
    """
    return float(num_qubits * num_qubits)


def product_state_qfi(num_qubits: int) -> float:
    """Standard quantum limit: QFI = N for product state."""
    return float(num_qubits)


class ModernQSense:
    def __init__(self, num_qubits: int) -> None:
        self.num_qubits = num_qubits

    def metrology(self, num_measurements: int = 1000, use_ghz: bool = True) -> Dict[str, float]:
        qfi = ghz_qfi(self.num_qubits) if use_ghz else product_state_qfi(self.num_qubits)
        classical_std = 1.0 / np.sqrt(num_measurements)
        quantum_std = 1.0 / np.sqrt(qfi * num_measurements)
        return {
            "quantum_fisher_information": qfi,
            "classical_std": float(classical_std),
            "quantum_std": float(quantum_std),
            "quantum_advantage": float(classical_std / quantum_std),
            "heisenberg_scaling": (
                1.0 / self.num_qubits if use_ghz else 1.0 / np.sqrt(self.num_qubits)
            ),
        }
