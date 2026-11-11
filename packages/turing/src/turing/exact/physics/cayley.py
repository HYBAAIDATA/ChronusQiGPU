"""
Turing Exact Quantum Library — Exact Evolution & Cayley Unitary Dynamics
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Union
from turing.exact.errors import DimensionMismatchError
from turing.exact.ring.zeta import ZetaP
from turing.exact.ring.matrix import MatrixZetaP
from turing.exact.core.unitary import UnitaryZetaP
from turing.exact.core.obstruction import Obstruction


@dataclass(frozen=True)
class ContinuousSchedule:
    """Continuous time schedule requiring transcendental Trotterized evolution."""
    total_time: float


def discrete_evolution(unitaries: List[UnitaryZetaP]) -> UnitaryZetaP:
    """Computes exact composite unitary evolution through a sequence of discrete gates."""
    if len(unitaries) == 0:
        raise DimensionMismatchError("Unitary sequence must not be empty")
    res = UnitaryZetaP.identity(unitaries[0].dimension, unitaries[0].p)
    for U in unitaries:
        res = res.compose(U)
    return res


def continuous_adiabatic(H: MatrixZetaP, schedule: ContinuousSchedule) -> Obstruction:
    """Formal obstruction: continuous adiabatic evolution exp(-iHs) is transcendental."""
    return Obstruction(
        primitive="adiabatic_evolution",
        value="exp(-i * H * s)",
        ring="none (transcendental continuous schedule)",
        message="continuous adiabatic evolution is transcendental; exact evolution is the discrete product of unitaries"
    )


def cayley_evolution(H: MatrixZetaP) -> Union[Tuple[MatrixZetaP, int], Obstruction]:
    """
    Exact algebraic Cayley transform U = (I - H)(I + H)^(-1) for anti-Hermitian H (H† = -H).
    Eliminates continuous Trotter truncation error and transcendental exponentials.
    Returns (U_num, scale_norm) as a projective unitary where U_num† * U_num == scale_norm * I.
    """
    I = MatrixZetaP.identity(H.rows, H.p)
    I_plus_H = I + H
    det_plus = I_plus_H.det()
    if det_plus == ZetaP.zero(H.p):
        return Obstruction(
            primitive="cayley_evolution",
            value="singular_cayley_resolvent",
            ring="none",
            message="det(I + H) is zero; Cayley resolvent singular"
        )

    neg_H = MatrixZetaP(H.rows, H.cols, [[-e for e in row] for row in H.entries], H.p)
    if H.dagger() != neg_H:
        return Obstruction(
            primitive="cayley_evolution",
            value="non_anti_hermitian",
            ring="Z[zeta_p]",
            message="Generator H must be anti-Hermitian (H† = -H)"
        )

    I_minus_H = I + neg_H
    adj_plus = I_plus_H.adjugate()
    U_num = I_minus_H * adj_plus
    det_norm_sq = det_plus * det_plus.conjugate()
    scale_norm = det_norm_sq.coeffs[0] if all(c == 0 for c in det_norm_sq.coeffs[1:]) else det_norm_sq.norm()
    return (U_num, scale_norm)
