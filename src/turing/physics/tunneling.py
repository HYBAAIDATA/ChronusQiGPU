"""
Turing Exact Quantum Library — Exact Tight-Binding Transfer Matrix & Tunneling
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union
from turing.errors import NonUnitError
from turing.ring.zeta import ZetaP
from turing.ring.rational import RationalZetaP
from turing.ring.matrix import MatrixZetaP
from turing.core.obstruction import Obstruction


@dataclass(frozen=True)
class DiscreteBarrier:
    """Discrete 1D lattice potential barrier with exact site potentials and hopping amplitude."""
    num_sites: int
    potential: List[ZetaP]
    hopping: ZetaP


@dataclass(frozen=True)
class ContinuousBarrier:
    """Continuous barrier model requiring transcendental analytical solutions."""
    length: float
    height: float


def transmission_coefficient(barrier: Union[DiscreteBarrier, ContinuousBarrier], energy: ZetaP) -> Union[ZetaP, Obstruction]:
    """
    Computes exact transmission coefficient in Z[zeta_p].
    Returns Obstruction for continuous barriers or when |T_11|^2 is not an algebraic unit.
    """
    if isinstance(barrier, ContinuousBarrier):
        return Obstruction(
            primitive="transmission_coefficient",
            value="exp(-kappa * L)",
            ring="none (transcendental continuum)",
            message="continuous barrier potential is an analytical obstruction; exact tunneling requires DiscreteBarrier"
        )

    p = energy.p
    if not barrier.hopping.is_unit():
        raise NonUnitError("Hopping parameter t must be a unit in Z[zeta_p] for exact transfer matrix")
    hopping_inv = barrier.hopping.inverse()

    T = MatrixZetaP.identity(2, p)
    for n in range(barrier.num_sites):
        m00 = (energy - barrier.potential[n]) * hopping_inv
        m01 = -ZetaP.one(p)
        m10 = ZetaP.one(p)
        m11 = ZetaP.zero(p)
        Mn = MatrixZetaP(2, 2, [[m00, m01], [m10, m11]], p)
        T = Mn * T

    t11 = T.entries[0][0]
    denom = t11 * t11.conjugate()
    if not denom.is_unit():
        return Obstruction(
            primitive="transmission_coefficient",
            value=f"|T_11|^2={denom} is not a unit",
            ring="the ring where |T_11|^2 is a unit",
            message="discrete transmission coefficient is exact over the ring only when |T_11|^2 is a unit"
        )
    return denom.inverse()


def transmission_coefficient_exact(barrier: Union[DiscreteBarrier, ContinuousBarrier], energy: ZetaP) -> Union[RationalZetaP, Obstruction]:
    """
    Exact transmission coefficient in the cyclotomic field of fractions Q(zeta_p).
    Lifts the ring unit obstruction to exact field inversion.
    """
    if isinstance(barrier, ContinuousBarrier):
        return Obstruction(
            primitive="transmission_coefficient",
            value="exp(-kappa * L)",
            ring="none (transcendental continuum)",
            message="continuous barrier potential is an analytical obstruction; exact tunneling requires DiscreteBarrier"
        )

    p = energy.p
    if not barrier.hopping.is_unit():
        raise NonUnitError("Hopping parameter t must be a unit in Z[zeta_p] for exact transfer matrix")
    hopping_inv = barrier.hopping.inverse()

    T = MatrixZetaP.identity(2, p)
    for n in range(barrier.num_sites):
        m00 = (energy - barrier.potential[n]) * hopping_inv
        m01 = -ZetaP.one(p)
        m10 = ZetaP.one(p)
        m11 = ZetaP.zero(p)
        Mn = MatrixZetaP(2, 2, [[m00, m01], [m10, m11]], p)
        T = Mn * T

    t11 = T.entries[0][0]
    denom = t11 * t11.conjugate()
    if denom == ZetaP.zero(p):
        return Obstruction(
            primitive="transmission_coefficient",
            value="0",
            ring="none",
            message="Total reflection: transmission coefficient denominator is zero"
        )
    return denom.field_inverse()
