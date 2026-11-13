"""Exact algebraic arithmetic for TURING.

Amplitudes are elements of cyclotomic fields Q(zeta_n), subfields of the
complex numbers, stored with exact rational coordinates (zero rounding).
:mod:`turing.algebra.reduction` provides exact residue checksums into finite
fields; residues never replace amplitudes.
"""

from .cyclotomic import (
    CyclotomicElement,
    CyclotomicField,
    abs2_of_progression,
    abs2_of_root_sum,
    cyclotomic_polynomial,
    divisors,
    euler_phi,
    factorize,
    is_prime,
    mobius,
    pairwise_difference_counts,
    progression_difference_counts,
)
from .reduction import (
    CyclotomicResidueMap,
    f257_residue_map,
    inverse_mod,
    multiplicative_order,
)

__all__ = [
    "CyclotomicElement",
    "CyclotomicField",
    "CyclotomicResidueMap",
    "abs2_of_progression",
    "abs2_of_root_sum",
    "cyclotomic_polynomial",
    "divisors",
    "euler_phi",
    "f257_residue_map",
    "factorize",
    "inverse_mod",
    "is_prime",
    "mobius",
    "multiplicative_order",
    "pairwise_difference_counts",
    "progression_difference_counts",
]
