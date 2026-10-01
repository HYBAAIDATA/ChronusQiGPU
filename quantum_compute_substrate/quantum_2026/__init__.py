"""2026 state-of-the-art quantum-mathematical algorithms.

Substrate-agnostic implementations of:
  * VQE with true QFIM natural gradient, ADAPT operator pool, ZNE.
  * QAOA with Egger warm-start, multi-angle, recursive elimination.
  * QML with data re-uploading, projected quantum kernel.
  * Quantum simulation with 4th-order Suzuki-Trotter and qDRIFT.
  * Continuous-time and Szegedy discrete-time quantum walks.
  * Quantum metrology at the Heisenberg limit (GHZ QFI = N^2).
  * Reverse annealing, pause-and-quench.
  * Surface-code metrics with proper distance scaling.
  * Hybrid quantum-classical feedback loops.
"""

from .circuit_metrics import QuantumCircuitMetrics, QuantumAlgorithmType
from .vqe import (
    ModernVQE,
    adapt_operator_pool,
    parameter_shift_gradient,
    quantum_fisher_information_matrix,
    zero_noise_extrapolate,
)
from .qaoa import ModernQAOA, egger_warm_start_angles, multi_angle_qaoa_params
from .qml import ModernQML, quantum_kernel_matrix, projected_quantum_kernel
from .qsim import ModernQSim, suzuki_trotter_4th_order, qdrift_channel
from .qwalk import ModernQWalk, szegedy_walk_operator
from .qsense import ModernQSense, ghz_qfi, product_state_qfi
from .qanneal import ModernQAnneal
from .qec import ModernQEC, surface_code_logical_error_rate
from .hybrid import ModernHybrid

__all__ = [
    "QuantumCircuitMetrics",
    "QuantumAlgorithmType",
    "ModernVQE",
    "adapt_operator_pool",
    "parameter_shift_gradient",
    "quantum_fisher_information_matrix",
    "zero_noise_extrapolate",
    "ModernQAOA",
    "egger_warm_start_angles",
    "multi_angle_qaoa_params",
    "ModernQML",
    "quantum_kernel_matrix",
    "projected_quantum_kernel",
    "ModernQSim",
    "suzuki_trotter_4th_order",
    "qdrift_channel",
    "ModernQWalk",
    "szegedy_walk_operator",
    "ModernQSense",
    "ghz_qfi",
    "product_state_qfi",
    "ModernQAnneal",
    "ModernQEC",
    "surface_code_logical_error_rate",
    "ModernHybrid",
    "EnhancedGrover",
    "GroverMetrics",
    "optimal_grover_iterations",
    "apply_diffusion",
    "apply_oracle",
    "fixed_point_amplitude_amplification",
    "quantum_counting_estimate",
    "EnhancedShor",
    "ShorMetrics",
    "continued_fraction_convergents",
    "extract_period_from_phase",
    "quantum_period_finding_matrix",
    "EnhancedQFT",
    "exact_qft_matrix",
    "banded_qft_matrix",
    "coppersmith_error_bound",
]

from .classics import (
    EnhancedGrover,
    GroverMetrics,
    optimal_grover_iterations,
    apply_diffusion,
    apply_oracle,
    fixed_point_amplitude_amplification,
    quantum_counting_estimate,
    EnhancedShor,
    ShorMetrics,
    continued_fraction_convergents,
    extract_period_from_phase,
    quantum_period_finding_matrix,
    EnhancedQFT,
    exact_qft_matrix,
    banded_qft_matrix,
    coppersmith_error_bound,
)
