"""Enhanced classic quantum algorithms - Grover, Shor, QFT.

Tribute: To Lov Grover, Peter Shor, Don Coppersmith, and the pioneers.
"""
from .grover import (
    EnhancedGrover, GroverMetrics,
    optimal_grover_iterations, apply_diffusion, apply_oracle,
    fixed_point_amplitude_amplification, quantum_counting_estimate,
)
from .shor import (
    EnhancedShor, ShorMetrics,
    continued_fraction_convergents, extract_period_from_phase,
    quantum_period_finding_matrix,
)
from .qft import (
    EnhancedQFT, exact_qft_matrix, banded_qft_matrix,
    coppersmith_error_bound,
)

__all__ = [
    "EnhancedGrover", "GroverMetrics", "optimal_grover_iterations",
    "apply_diffusion", "apply_oracle", "fixed_point_amplitude_amplification",
    "quantum_counting_estimate",
    "EnhancedShor", "ShorMetrics", "continued_fraction_convergents",
    "extract_period_from_phase", "quantum_period_finding_matrix",
    "EnhancedQFT", "exact_qft_matrix", "banded_qft_matrix",
    "coppersmith_error_bound",
]
