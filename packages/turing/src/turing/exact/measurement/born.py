"""
Turing Exact Quantum Library — Exact Quantum Measurement Postulates
"""

from __future__ import annotations
from typing import Tuple, Union
from turing.exact.errors import StateNormError, DimensionMismatchError
from turing.exact.ring.utils import gcd
from turing.exact.ring.zeta import ZetaP
from turing.exact.core.state import StateZetaP, inner_product
from turing.exact.core.obstruction import Obstruction


def born_probability(state: StateZetaP, basis_index: int) -> ZetaP:
    """Computes exact Born probability amplitude |a_i|^2 in Z[zeta_p]."""
    if not (0 <= basis_index < state.dimension):
        raise DimensionMismatchError(f"Basis index {basis_index} out of range for dimension {state.dimension}")
    a = state.vector[basis_index]
    return a * a.conjugate()


def project(state: StateZetaP, basis_index: int) -> StateZetaP:
    """Exact projective collapse onto the standard basis state |basis_index>."""
    if not (0 <= basis_index < state.dimension):
        raise DimensionMismatchError(f"Basis index {basis_index} out of range for dimension {state.dimension}")
    return StateZetaP.basis(basis_index, state.dimension, state.p)


def sum_born_probabilities(state: StateZetaP) -> ZetaP:
    """Computes total unnormalized probability weight sum_i |a_i|^2 in Z[zeta_p]."""
    res = ZetaP.zero(state.p)
    for i in range(state.dimension):
        res = res + born_probability(state, i)
    return res


def projective_born_probability(state: StateZetaP, outcome: int) -> Tuple[int, int]:
    """
    Calculates exact reduced rational measurement probability (num, den) in Q.
    Demonstrates that projective scale norms cancel identically upon measurement.
    """
    if not (0 <= outcome < state.dimension):
        raise DimensionMismatchError(f"Outcome index {outcome} out of bounds for dimension {state.dimension}")
    num = born_probability(state, outcome)
    denom = sum_born_probabilities(state)
    if denom == ZetaP.zero(state.p):
        raise StateNormError("State has zero norm")

    # If both num and denom are integers (pure scalar coefficients)
    if all(c == 0 for c in num.coeffs[1:]) and all(c == 0 for c in denom.coeffs[1:]):
        n_val = num.coeffs[0]
        d_val = denom.coeffs[0]
        g = gcd(n_val, d_val)
        return (n_val // g, d_val // g)

    rat = denom.field_inverse() * num
    n_val = rat.num.coeffs[0]
    d_val = rat.den
    g = gcd(n_val, d_val)
    return (n_val // g, d_val // g)


def visibility(psi: StateZetaP, phi: StateZetaP) -> Union[ZetaP, Obstruction]:
    """
    Computes exact quantum visibility |<psi|phi>|^2 / (<psi|psi><phi|phi>).
    Returns an Obstruction if the state norms are not algebraic units.
    """
    norm_sq_psi = psi.norm_squared()
    norm_sq_phi = phi.norm_squared()
    if not norm_sq_psi.is_unit() or not norm_sq_phi.is_unit():
        return Obstruction(
            primitive="visibility",
            value="denominator is not a unit",
            ring="the ring where the norms are units",
            message="visibility is defined on states whose norm squared values are units"
        )
    inner = inner_product(psi, phi)
    numerator = inner * inner.conjugate()
    denominator = norm_sq_psi * norm_sq_phi
    return numerator * denominator.inverse()
