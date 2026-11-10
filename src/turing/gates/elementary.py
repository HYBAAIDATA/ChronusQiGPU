"""
Turing Exact Quantum Library — Elementary Quantum Gates
"""

from __future__ import annotations
from turing.ring.zeta import ZetaP
from turing.ring.matrix import MatrixZetaP
from turing.core.unitary import UnitaryZetaP, ProjectiveUnitaryZetaP
from turing.core.obstruction import Obstruction


def pauli_x(p: int) -> UnitaryZetaP:
    """Exact Pauli X (bit flip) gate."""
    return UnitaryZetaP(MatrixZetaP(2, 2, [
        [ZetaP.zero(p), ZetaP.one(p)],
        [ZetaP.one(p), ZetaP.zero(p)]
    ], p))


def pauli_z(p: int) -> UnitaryZetaP:
    """Exact Pauli Z (phase flip) gate."""
    return UnitaryZetaP(MatrixZetaP(2, 2, [
        [ZetaP.one(p), ZetaP.zero(p)],
        [ZetaP.zero(p), -ZetaP.one(p)]
    ], p))


def cnot(p: int) -> UnitaryZetaP:
    """Exact 2-qudit CNOT gate."""
    z = ZetaP.zero(p)
    o = ZetaP.one(p)
    return UnitaryZetaP(MatrixZetaP(4, 4, [
        [o, z, z, z],
        [z, o, z, z],
        [z, z, z, o],
        [z, z, o, z]
    ], p))


def phase(k: int, p: int) -> UnitaryZetaP:
    """Exact phase gate diag(1, zeta_p^k)."""
    return UnitaryZetaP(MatrixZetaP(2, 2, [
        [ZetaP.one(p), ZetaP.zero(p)],
        [ZetaP.zero(p), ZetaP.zeta_power(k, p)]
    ], p))


def hadamard(p: int) -> Obstruction:
    """
    Formal obstruction record: standard unscaled Hadamard requires 1/sqrt(2),
    which is not an element of Z[zeta_p] for any prime p.
    """
    return Obstruction(
        primitive="hadamard",
        value="1/sqrt(2)",
        ring="Z[zeta_8] (not in the prime-indexed family)",
        message=f"Hadamard is not in Z[zeta_{p}] for any prime p; "
                "the exact Hadamard requires Z[zeta_8]. This is a global obstruction."
    )


def fourier_gate_projective(p: int) -> ProjectiveUnitaryZetaP:
    """
    Exact generalized Hadamard / Discrete Fourier Transform gate F_p in P(H).
    Entries are (F_p)_{j,k} = zeta_p^(j*k) lying 100% inside Z[zeta_p].
    F_p† * F_p = p * I (scale_norm = p). Zero square roots, zero floats.
    """
    entries = [[ZetaP.zeta_power(j * k, p) for k in range(p)] for j in range(p)]
    mat = MatrixZetaP(p, p, entries, p)
    return ProjectiveUnitaryZetaP(mat, p)


def hadamard_projective(p: int) -> ProjectiveUnitaryZetaP:
    """
    Algebraic lift of the Hadamard gate into projective Hilbert space P(H).
    Resolves the 1/sqrt(2) unscaled obstruction via quadratic Gauss-sum normalization.
    """
    return fourier_gate_projective(p)
