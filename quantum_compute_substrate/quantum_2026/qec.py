"""Surface-code metrics with correct threshold scaling.

p_L(d) = A * (p / p_th) ** ((d + 1) / 2)   [Fowler et al. 2012]
for p < p_th, where p_th ~ 0.01 for the standard surface code.
"""
from __future__ import annotations
from typing import Dict


def surface_code_logical_error_rate(physical_error_rate: float,
                                    code_distance: int,
                                    threshold: float = 0.01,
                                    prefactor: float = 0.03) -> float:
    if physical_error_rate <= 0:
        return 0.0
    if physical_error_rate >= threshold:
        return 1.0
    return prefactor * (physical_error_rate / threshold) ** ((code_distance + 1) / 2.0)


class ModernQEC:
    def __init__(self, code_distance: int) -> None:
        if code_distance < 1 or code_distance % 2 == 0:
            raise ValueError("code distance must be a positive odd integer")
        self.code_distance = code_distance
        self.physical_qubits = 2 * code_distance * code_distance - 1

    def surface_code_metrics(self, physical_error_rate: float = 1e-3,
                             threshold: float = 0.01) -> Dict:
        pL = surface_code_logical_error_rate(physical_error_rate, self.code_distance,
                                             threshold=threshold)
        return {
            "code_distance": self.code_distance,
            "physical_qubits": self.physical_qubits,
            "logical_qubits": 1,
            "threshold_error_rate": threshold,
            "physical_error_rate": physical_error_rate,
            "logical_error_rate": pL,
            "error_suppression_factor": (physical_error_rate / threshold) ** ((self.code_distance + 1) / 2.0),
            "correctable_errors": (self.code_distance - 1) // 2,
        }

    def fault_tolerant_gate_cost(self, gate: str) -> Dict[str, int]:
        table = {
            "H": {"physical_gates": 1, "time_steps": 1},
            "CNOT": {"physical_gates": 2, "time_steps": 2},
            "T": {"physical_gates": 100, "time_steps": 50},
            "Toffoli": {"physical_gates": 1000, "time_steps": 500},
            "S": {"physical_gates": 1, "time_steps": 1},
        }
        return table.get(gate, {"physical_gates": 10, "time_steps": 5})
