# LUCAS WIRING: mtheory
# Substrate route: mtheory
"""mtheory — exact mathematics of M-theory compactifications and dualities.

Exact int/Fraction arithmetic only: KK towers on T^7, T/S/U-duality group
actions on truncated spectra, the five-limits permutation table, and the
exact 11-qubit Hilbert-space register over Q(i, sqrt(2)) (C^2048).
No floats, no approximation, no simulation.
"""

from .kk_spectrum import KKTower, MILLENNIUM_BOUNDS, SECTOR_RADII
from .hilbert import (
    ExactComplex,
    GroverExact,
    QuantumRegister,
    QSqrt,
    QSqrt2,
    cnot_matrix,
    fourier_matrix,
    hadamard_matrix,
    matrices_equal,
    matmul,
    pauli_x_matrix,
    pauli_z_matrix,
    phase_s_matrix,
    phase_t_matrix,
    qft,
    reduced_density_matrix,
    verify_unitary,
    von_neumann_entropy_exact,
)
from .duality import (
    FIVE_LIMITS,
    bosonic_spectrum,
    circle_spectrum,
    coupling_from_tau,
    eleven_d_coupling,
    iia_to_11d,
    s_dualize,
    sl2z_act,
    sl2z_compose,
    t_dualize,
    tau_from_coupling,
    u_dualize,
    verify_iia_11d,
    verify_s_duality,
    verify_t_duality,
    verify_u_duality,
)

__all__ = [
    "KKTower",
    "MILLENNIUM_BOUNDS",
    "SECTOR_RADII",
    "ExactComplex",
    "GroverExact",
    "QuantumRegister",
    "QSqrt",
    "QSqrt2",
    "cnot_matrix",
    "fourier_matrix",
    "hadamard_matrix",
    "matrices_equal",
    "matmul",
    "pauli_x_matrix",
    "pauli_z_matrix",
    "phase_s_matrix",
    "phase_t_matrix",
    "qft",
    "reduced_density_matrix",
    "verify_unitary",
    "von_neumann_entropy_exact",
    "FIVE_LIMITS",
    "bosonic_spectrum",
    "circle_spectrum",
    "coupling_from_tau",
    "eleven_d_coupling",
    "iia_to_11d",
    "s_dualize",
    "sl2z_act",
    "sl2z_compose",
    "t_dualize",
    "tau_from_coupling",
    "u_dualize",
    "verify_iia_11d",
    "verify_s_duality",
    "verify_t_duality",
    "verify_u_duality",
]
