"""Generative rules -- deterministic functions that give T[i0..i5] in O(rank).

We never materialize the tensor. These rules define it implicitly.
"""

from __future__ import annotations
import cmath
import math
from dataclasses import dataclass
from typing import Sequence

PHI_FLOAT = (1 + math.sqrt(5)) / 2


@dataclass(frozen=True)
class PhiCharacterRule:
    """Rule: T[i0..i5] = exp(2 pi i / N * sum_k phi^k * i_k) / sqrt(N^rank).

    N is the axis length. This is a phi-weighted multiplicative character on
    Z_N^6. Every element has magnitude 1 / sqrt(N^rank), and slices are exactly
    Kloosterman-like sums.
    """

    N: int
    rank: int = 6

    def __post_init__(self) -> None:
        if self.N < 2:
            raise ValueError("N must be >= 2")
        if self.rank < 1:
            raise ValueError("rank must be >= 1")

    def phi_weight(self, axis: int) -> float:
        return PHI_FLOAT**axis

    def normalization(self) -> float:
        """1 / sqrt(N^rank)."""
        # sqrt(N)^rank in log space to avoid overflow for astronomical N^rank.
        return math.exp(-0.5 * self.rank * math.log(self.N))

    def element(self, indices: Sequence[int]) -> complex:
        if len(indices) != self.rank:
            raise ValueError(f"expected {self.rank} indices, got {len(indices)}")
        s = 0.0
        for k, i in enumerate(indices):
            if not 0 <= i < self.N:
                raise IndexError(f"axis {k} index {i} out of range [0, {self.N})")
            s += self.phi_weight(k) * i
        phase = 2 * math.pi * (s / self.N)
        return complex(cmath.exp(1j * phase)) * self.normalization()

    def slice_of_axis(self, axis: int, other_indices: Sequence[int]) -> callable:
        """Return a callable f(i) that gives T[..., i (at axis), ...].
        Length of slice = N. Never materialize the whole slice unless asked.
        """
        if len(other_indices) != self.rank - 1:
            raise ValueError("need rank-1 other indices")
        fixed = list(other_indices)

        def f(i: int) -> complex:
            full = fixed[:axis] + [i] + fixed[axis:]
            return self.element(full)

        return f


@dataclass(frozen=True)
class RankOneRule:
    """Rule: T[i0..i5] = prod_k f_k(i_k) for factor functions f_k.

    A rank-1 tensor is defined by rank factor vectors. Storable in O(rank*N)
    if desired. Contraction of any two axes just multiplies through.
    """

    N: int
    rank: int = 6

    def factor_value(self, axis: int, i: int) -> complex:
        # phi-fold factor: f_k(i) = exp(2 pi i * F(k+1) / N * i)
        # (Uses Fibonacci number instead of phi power for exact-integer phase.)
        from .phi_identities import fib

        k = fib(axis + 1)
        return cmath.exp(2j * math.pi * (k * i) / self.N)

    def element(self, indices: Sequence[int]) -> complex:
        if len(indices) != self.rank:
            raise ValueError(f"expected {self.rank} indices")
        out = 1.0 + 0j
        for axis, i in enumerate(indices):
            out *= self.factor_value(axis, i)
        # Normalize so |T|^2 sums to 1 (rank-1 pure state):
        norm = math.exp(-0.5 * self.rank * math.log(self.N))
        return out * norm
