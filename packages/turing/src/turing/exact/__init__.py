"""
Turing — Exact Algebraic Quantum Substrate
==========================================
Discrete quantum mechanics over cyclotomic integer rings Z[zeta_p]
and fraction fields Q(zeta_p). Zero floating point drift, exact Galois norms,
projective Hilbert space P(H), and symplectic qudit stabilizer tableaus.
"""

__version__ = "0.1.0"

from turing.exact.errors import (
    TuringError,
    RingError,
    NonUnitError,
    DimensionMismatchError,
    StateNormError,
    AlgebraicObstructionError,
)

from turing.exact.ring.utils import (
    is_prime,
    gcd,
    legendre_symbol,
    cyclotomic_polynomial_prime,
    convolution,
    bareiss_det,
)
from turing.exact.ring.zeta import ZetaP
from turing.exact.ring.rational import RationalZetaP
from turing.exact.ring.matrix import MatrixZetaP

from turing.exact.core.obstruction import Obstruction
from turing.exact.core.state import (
    StateZetaP,
    superpose,
    inner_product,
    amplitude,
)
from turing.exact.core.unitary import (
    UnitaryZetaP,
    ProjectiveUnitaryZetaP,
)

from turing.exact.gates.elementary import (
    pauli_x,
    pauli_z,
    cnot,
    phase,
    hadamard,
    fourier_gate_projective,
    hadamard_projective,
)

from turing.exact.measurement.born import (
    born_probability,
    project,
    sum_born_probabilities,
    projective_born_probability,
    visibility,
)

from turing.exact.entanglement.schmidt import (
    matrix_rank_over_field,
    schmidt_rank,
    normalized_schmidt_coefficients,
    reduced_density_gram,
    exact_renyi_purity,
)

from turing.exact.physics.tunneling import (
    DiscreteBarrier,
    ContinuousBarrier,
    transmission_coefficient,
    transmission_coefficient_exact,
)
from turing.exact.physics.cayley import (
    ContinuousSchedule,
    discrete_evolution,
    continuous_adiabatic,
    cayley_evolution,
)
from turing.exact.physics.swarm import (
    SwarmZetaP,
    quantum_inspired_metaheuristic,
)

from turing.exact.stabilizer.tableau import StabilizerTableauZetaP

__all__ = [
    "__version__",
    "TuringError",
    "RingError",
    "NonUnitError",
    "DimensionMismatchError",
    "StateNormError",
    "AlgebraicObstructionError",
    "is_prime",
    "gcd",
    "legendre_symbol",
    "cyclotomic_polynomial_prime",
    "convolution",
    "bareiss_det",
    "ZetaP",
    "RationalZetaP",
    "MatrixZetaP",
    "Obstruction",
    "StateZetaP",
    "superpose",
    "inner_product",
    "amplitude",
    "UnitaryZetaP",
    "ProjectiveUnitaryZetaP",
    "pauli_x",
    "pauli_z",
    "cnot",
    "phase",
    "hadamard",
    "fourier_gate_projective",
    "hadamard_projective",
    "born_probability",
    "project",
    "sum_born_probabilities",
    "projective_born_probability",
    "visibility",
    "matrix_rank_over_field",
    "schmidt_rank",
    "normalized_schmidt_coefficients",
    "reduced_density_gram",
    "exact_renyi_purity",
    "DiscreteBarrier",
    "ContinuousBarrier",
    "transmission_coefficient",
    "transmission_coefficient_exact",
    "ContinuousSchedule",
    "discrete_evolution",
    "continuous_adiabatic",
    "cayley_evolution",
    "SwarmZetaP",
    "quantum_inspired_metaheuristic",
    "StabilizerTableauZetaP",
]
