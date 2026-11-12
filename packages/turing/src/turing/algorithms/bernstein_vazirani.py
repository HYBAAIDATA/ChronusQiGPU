"""Bernstein-Vazirani: exact recovery of s from the oracle x -> s.x xor b.

After H^n U_f H^n the amplitude of |y> is (-1)^b [y = s], so s is returned
with probability exactly 1. The oracle is verified to be affine first.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .oracles import boolean_table, require_affine, require_qubit_domain
from .walsh import phase_oracle_amplitudes

__all__ = ["BernsteinVaziraniResult", "run"]


@dataclass(frozen=True)
class BernsteinVaziraniResult:
    num_inputs: int
    hidden_string: int
    offset: int
    probability: Fraction
    distribution: tuple[Fraction, ...]


def run(n: int, oracle: object) -> BernsteinVaziraniResult:
    """Return s with its exact probability; ValueError unless f(x) = s.x xor b."""
    require_qubit_domain(oracle, n)
    table = boolean_table(oracle)
    s_check, b = require_affine(table, n)
    amplitudes = phase_oracle_amplitudes(table)
    distribution = tuple(a * a for a in amplitudes)
    support = [y for y, p in enumerate(distribution) if p]
    if len(support) != 1:
        raise ArithmeticError(f"expected a single outcome with nonzero probability, found {len(support)}")
    s = support[0]
    if s != s_check:
        raise ArithmeticError("exact evaluation disagrees with the classical oracle check")
    return BernsteinVaziraniResult(num_inputs=n, hidden_string=s, offset=b, probability=distribution[s],
                                   distribution=distribution)
