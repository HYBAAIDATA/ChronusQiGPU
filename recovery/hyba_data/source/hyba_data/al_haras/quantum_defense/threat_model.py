"""Quantum Adversary Threat Model — what we defend against."""
from dataclasses import dataclass
from typing import Dict


@dataclass
class QuantumAdversaryCapabilities:
    can_simulate_complex_systems: bool = True
    simulation_depth: int = 1000
    can_optimize_attack_paths: bool = True
    optimization_parallelism_divisor: float = 1.0
    can_undermine_classical_randomness: bool = True
    random_break_speedup: float = 100.0
    can_accelerate_brute_force: bool = True
    search_speedup: float = 100.0
    qubits: int = 1000
    fidelity: float = 1.0

    def assess(self) -> Dict:
        score = 0.25 * min(1.0, self.simulation_depth / 1000) + 0.25 * min(1.0, self.optimization_parallelism_divisor) + 0.25 * min(1.0, self.search_speedup / 100.0) + 0.25 * min(1.0, self.qubits / 1000)
        return {'threat_score': round(score, 3), 'classification': 'CRITICAL' if score > 0.7 else 'HIGH', 'can_penetrate_classical': score > 0.3, 'requires_quantum_defense': True}


class ClassicalDefenseModel:
    """Classical defense assumptions — all broken by quantum adversaries."""

    def __init__(self):
        self.assumptions = {'bounded_compute': True, 'static_attack_trees': True, 'linear_search': True, 'randomness_secure': True, 'no_quantum_acceleration': True}

    def validate(self) -> Dict:
        return {'valid_against_classical': True, 'valid_against_quantum': False, 'failure_points': ['Bounded compute violated by superposition', 'Static trees cannot model quantum search', 'Linear search becomes O(sqrt(N)) with Grover', 'Randomness undermined by quantum estimation', 'Quantum acceleration changes all assumptions'], 'requires_new_defense': True}
