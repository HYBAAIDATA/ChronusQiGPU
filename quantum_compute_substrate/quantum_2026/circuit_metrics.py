"""Circuit-level metrics and algorithm taxonomy."""

from dataclasses import dataclass
from enum import Enum


class QuantumAlgorithmType(Enum):
    VQE = "variational_quantum_eigensolver"
    QAOA = "quantum_approximate_optimization"
    QML = "quantum_machine_learning"
    QSIM = "quantum_simulation"
    QWALK = "quantum_walk"
    QSENSE = "quantum_sensing"
    QANNEAL = "quantum_annealing"
    QNEURON = "quantum_neural_network"
    HYBRID = "hybrid_quantum_classical"
    ADAPTIVE = "adaptive_quantum"


@dataclass(frozen=True)
class QuantumCircuitMetrics:
    circuit_depth: int
    gate_count: int
    two_qubit_gates: int
    estimated_error_rate: float
    coherence_time_required: float
    fidelity_estimate: float
    quantum_volume_requirement: int

    def is_nisq_feasible(self, coherence_budget: float, error_budget: float) -> bool:
        return (
            self.coherence_time_required <= coherence_budget
            and self.estimated_error_rate <= error_budget
        )
