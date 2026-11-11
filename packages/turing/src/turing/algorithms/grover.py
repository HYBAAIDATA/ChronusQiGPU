"""Grover search with exact amplitudes and lossless folding.

Every marked item carries the same amplitude and so does every unmarked item,
so the state lies exactly in the span of the uniform marked vector and the
uniform unmarked vector. Amplitudes are written as A / sqrt(N) with A an exact
Fraction (1/sqrt(N) stays symbolic); probabilities A^2 / N are exact Fractions.

One iteration is the oracle (sign flip on marked items) followed by the
diffusion 2|s><s| - I. With integer numerators over N^k:
alpha' = (N - 2M) alpha + 2 (N - M) beta,  beta' = -2M alpha + (N - 2M) beta.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import isqrt
from typing import Iterable

from .oracles import boolean_table

__all__ = [
    "GroverSearchResult",
    "GroverState",
    "folded_grover",
    "optimal_iterations",
    "search",
    "success_probability",
    "unfolded_grover",
]


def _check_counts(num_items: int, num_marked: int, iterations: int) -> None:
    for name, value in (("num_items", num_items), ("num_marked", num_marked), ("iterations", iterations)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an int")
    if num_items < 1:
        raise ValueError("num_items must be at least 1")
    if not 0 <= num_marked <= num_items:
        raise ValueError("num_marked must lie in 0 .. num_items")
    if iterations < 0:
        raise ValueError("iterations must be non-negative")


@dataclass(frozen=True)
class GroverState:
    """Folded state after k iterations; each amplitude is value / sqrt(num_items)."""

    num_items: int
    num_marked: int
    iterations: int
    marked_amplitude: Fraction
    unmarked_amplitude: Fraction

    @property
    def marked_item_probability(self) -> Fraction:
        return self.marked_amplitude * self.marked_amplitude / self.num_items

    @property
    def unmarked_item_probability(self) -> Fraction:
        return self.unmarked_amplitude * self.unmarked_amplitude / self.num_items

    @property
    def success_probability(self) -> Fraction:
        return self.num_marked * self.marked_item_probability

    @property
    def failure_probability(self) -> Fraction:
        return (self.num_items - self.num_marked) * self.unmarked_item_probability


def _folded_numerators(num_items: int, num_marked: int, iterations: int) -> tuple[int, int]:
    alpha, beta = 1, 1
    a = num_items - 2 * num_marked
    b = 2 * (num_items - num_marked)
    c = -2 * num_marked
    for _ in range(iterations):
        alpha, beta = a * alpha + b * beta, c * alpha + a * beta
    return alpha, beta


def folded_grover(num_items: int, num_marked: int, iterations: int) -> GroverState:
    """Exact marked and unmarked amplitudes after ``iterations`` Grover iterations."""
    _check_counts(num_items, num_marked, iterations)
    alpha, beta = _folded_numerators(num_items, num_marked, iterations)
    scale = num_items ** iterations
    return GroverState(num_items, num_marked, iterations, Fraction(alpha, scale), Fraction(beta, scale))


def success_probability(num_items: int, num_marked: int, iterations: int) -> Fraction:
    return folded_grover(num_items, num_marked, iterations).success_probability


def unfolded_grover(num_items: int, marked: Iterable[int], iterations: int) -> tuple[Fraction, ...]:
    """Full-state evaluation: amplitude of every item, each written as value / sqrt(num_items)."""
    marked_set = set()
    for x in marked:
        if not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < num_items:
            raise ValueError(f"marked item {x!r} outside 0 .. {num_items - 1}")
        marked_set.add(x)
    _check_counts(num_items, len(marked_set), iterations)
    vector = [1] * num_items
    for _ in range(iterations):
        flipped = [-v if x in marked_set else v for x, v in enumerate(vector)]
        total2 = 2 * sum(flipped)
        vector = [total2 - num_items * v for v in flipped]
    scale = num_items ** iterations
    return tuple(Fraction(v, scale) for v in vector)


def optimal_iterations(num_items: int, num_marked: int) -> int:
    """Smallest k in 0 .. isqrt(N) + 1 maximising the exact success probability."""
    _check_counts(num_items, num_marked, 0)
    if num_marked == 0:
        return 0
    best_k = 0
    best = None
    a = num_items - 2 * num_marked
    b = 2 * (num_items - num_marked)
    c = -2 * num_marked
    alpha, beta = 1, 1
    for k in range(isqrt(num_items) + 2):
        if k:
            alpha, beta = a * alpha + b * beta, c * alpha + a * beta
        probability = Fraction(num_marked * alpha * alpha, num_items ** (2 * k + 1))
        if best is None or probability > best:
            best = probability
            best_k = k
    return best_k


@dataclass(frozen=True)
class GroverSearchResult:
    num_items: int
    marked: tuple[int, ...]
    iterations: int
    success_probability: Fraction
    item_probability: Fraction
    state: GroverState


def search(oracle: object) -> GroverSearchResult:
    """Exact Grover search: marked items, optimal iteration count and success probability.

    The oracle is evaluated on every basis state (the inputs its unitary acts
    on); the marked set defines the two folding classes.
    """
    table = boolean_table(oracle)
    num_items = len(table)
    marked = tuple(x for x, bit in enumerate(table) if bit)
    k = optimal_iterations(num_items, len(marked))
    state = folded_grover(num_items, len(marked), k)
    return GroverSearchResult(num_items=num_items, marked=marked, iterations=k,
                              success_probability=state.success_probability,
                              item_probability=state.marked_item_probability, state=state)
