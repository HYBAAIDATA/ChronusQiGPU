"""Simon's problem: exact outcome distribution and deterministic recovery of s.

The state after H^n, U_f and H^n on the first register is
sum_y sum_v (1/2^n) sum_{x: f(x) = v} (-1)^(x.y) |y>|v>. Folding the inputs by
their f-value is lossless: P(y) = (1/4^n) sum_d K(d) (-1)^(d.y), where
K(d) counts ordered pairs (x, x') with f(x) = f(x') and x xor x' = d.
Under Simon's promise P is uniform, 1/2^(n-1), on the orthogonal complement
of s (s != 0), or uniform 1/2^n when f is injective. The period s is
recovered by GF(2) elimination over the exact support; nothing is sampled.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .gf2 import nullspace, rank
from .oracles import function_table, require_qubit_domain, require_simon_promise
from .walsh import walsh_hadamard

__all__ = ["SimonResult", "outcome_distribution", "recover_period", "run"]


@dataclass(frozen=True)
class SimonResult:
    num_inputs: int
    distribution: tuple[Fraction, ...]
    support: tuple[int, ...]
    hidden_period: int
    support_rank: int


def outcome_distribution(n: int, oracle: object) -> tuple[Fraction, ...]:
    """Exact distribution of the first register (any oracle on n-bit inputs)."""
    require_qubit_domain(oracle, n)
    table = function_table(oracle)
    classes: dict[int, list[int]] = {}
    for x, value in enumerate(table):
        classes.setdefault(value, []).append(x)
    collisions = [0] * (1 << n)
    for members in classes.values():
        for x in members:
            for x2 in members:
                collisions[x ^ x2] += 1
    scale = 1 << (2 * n)
    return tuple(Fraction(v, scale) for v in walsh_hadamard(collisions))


def recover_period(n: int, support: tuple[int, ...]) -> int:
    """The unique s with s.y = 0 for every y in the support (0 when the support spans GF(2)^n)."""
    kernel = nullspace(support, n)
    if len(kernel) > 1:
        raise ValueError(f"support spans a subspace of codimension {len(kernel)}; s is not determined")
    return kernel[0] if kernel else 0


def run(n: int, oracle: object) -> SimonResult:
    """Validate Simon's promise, compute the exact distribution and recover s."""
    require_qubit_domain(oracle, n)
    promised = require_simon_promise(function_table(oracle), n)
    distribution = outcome_distribution(n, oracle)
    support = tuple(y for y, p in enumerate(distribution) if p)
    s = recover_period(n, support)
    if s != promised:
        raise ArithmeticError("recovered period disagrees with the classical promise check")
    return SimonResult(num_inputs=n, distribution=distribution, support=support, hidden_period=s,
                       support_rank=rank(support))
