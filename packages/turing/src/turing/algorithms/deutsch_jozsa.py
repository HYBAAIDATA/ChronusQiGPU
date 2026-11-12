"""Deutsch-Jozsa: exact evaluation of H^n U_f H^n on |0^n> with a phase oracle.

The amplitude of |y> is (1/2^n) sum_x (-1)^(f(x) + x.y), a rational number, so
the probability of |0^n> is an exact Fraction: 1 for a constant oracle and 0
for a balanced one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .oracles import boolean_table, require_constant_or_balanced, require_qubit_domain
from .walsh import phase_oracle_amplitudes

__all__ = ["DeutschJozsaResult", "run"]


@dataclass(frozen=True)
class DeutschJozsaResult:
    num_inputs: int
    amplitudes: tuple[Fraction, ...]
    probability_all_zero: Fraction
    verdict: str

    @property
    def distribution(self) -> tuple[Fraction, ...]:
        """Exact outcome distribution of the n-qubit register."""
        return tuple(a * a for a in self.amplitudes)


def run(n: int, oracle: object) -> DeutschJozsaResult:
    """Exact Deutsch-Jozsa evaluation; ValueError if the promise is violated."""
    require_qubit_domain(oracle, n)
    table = boolean_table(oracle)
    promised = require_constant_or_balanced(table)
    amplitudes = phase_oracle_amplitudes(table)
    probability = amplitudes[0] * amplitudes[0]
    if probability == 1:
        verdict = "constant"
    elif probability == 0:
        verdict = "balanced"
    else:
        raise ArithmeticError(f"probability of |0^n> is {probability}; expected exactly 0 or 1")
    if verdict != promised:
        raise ArithmeticError("exact evaluation disagrees with the classical promise check")
    return DeutschJozsaResult(num_inputs=n, amplitudes=amplitudes, probability_all_zero=probability,
                              verdict=verdict)
