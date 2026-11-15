"""Finite-dimensional complex linear operators and their basic properties."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .state import DEFAULT_TOLERANCE, QuantumState, _as_finite_complex


@dataclass(frozen=True, slots=True)
class LinearOperator:
    """A square complex matrix acting linearly on finite-dimensional kets."""

    matrix: tuple[tuple[complex, ...], ...]

    def __post_init__(self) -> None:
        rows = tuple(tuple(_as_finite_complex(value) for value in row) for row in self.matrix)
        if not rows or any(len(row) != len(rows) for row in rows):
            raise ValueError("operator matrix must be non-empty and square")
        object.__setattr__(self, "matrix", rows)

    @classmethod
    def from_rows(cls, rows: Iterable[Iterable[complex | float | int]]) -> "LinearOperator":
        return cls(tuple(tuple(_as_finite_complex(value) for value in row) for row in rows))

    @classmethod
    def identity(cls, dimension: int) -> "LinearOperator":
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
            raise ValueError("dimension must be a positive integer")
        return cls(tuple(tuple(1.0 + 0.0j if i == j else 0.0j for j in range(dimension))
                         for i in range(dimension)))

    @property
    def dimension(self) -> int:
        return len(self.matrix)

    def apply_amplitudes(self, amplitudes: tuple[complex, ...]) -> tuple[complex, ...]:
        """Apply this linear map to a vector without imposing normalization."""
        if len(amplitudes) != self.dimension:
            raise ValueError("operator and vector dimensions must match")
        values = tuple(_as_finite_complex(value) for value in amplitudes)
        return tuple(
            sum(self.matrix[i][j] * values[j] for j in range(self.dimension))
            for i in range(self.dimension)
        )

    def apply(self, state: QuantumState) -> QuantumState:
        """Apply this operator and require the result to be a normalized state.

        This convenience is appropriate for unitary evolution. General linear
        maps, including projectors that produce unnormalized vectors, should
        use :meth:`apply_amplitudes`.
        """
        if not isinstance(state, QuantumState):
            raise TypeError("state must be a QuantumState")
        return QuantumState(self.apply_amplitudes(state.amplitudes))

    def adjoint(self) -> "LinearOperator":
        return LinearOperator(tuple(
            tuple(self.matrix[j][i].conjugate() for j in range(self.dimension))
            for i in range(self.dimension)
        ))

    def compose(self, right: "LinearOperator") -> "LinearOperator":
        """Return ``self @ right`` (apply ``right`` first)."""
        if not isinstance(right, LinearOperator):
            raise TypeError("right must be a LinearOperator")
        if self.dimension != right.dimension:
            raise ValueError("operator dimensions must match")
        return LinearOperator(tuple(
            tuple(sum(self.matrix[i][k] * right.matrix[k][j]
                      for k in range(self.dimension))
                  for j in range(self.dimension))
            for i in range(self.dimension)
        ))

    def is_hermitian(self, tolerance: float = DEFAULT_TOLERANCE) -> bool:
        return self.almost_equal(self.adjoint(), tolerance)

    def is_unitary(self, tolerance: float = DEFAULT_TOLERANCE) -> bool:
        # Reject impossible columns before multiplying; large finite entries
        # must classify as non-unitary, not overflow an intermediate operator.
        if any(abs(value) > 1.0 + tolerance for row in self.matrix for value in row):
            return False
        try:
            return self.adjoint().compose(self).almost_equal(
                LinearOperator.identity(self.dimension), tolerance
            )
        except (ValueError, OverflowError):
            return False

    def almost_equal(self, other: "LinearOperator", tolerance: float = DEFAULT_TOLERANCE) -> bool:
        if not isinstance(other, LinearOperator) or self.dimension != other.dimension:
            return False
        return all(
            abs(self.matrix[i][j] - other.matrix[i][j]) <= tolerance
            for i in range(self.dimension)
            for j in range(self.dimension)
        )

    def expectation_value(self, state: QuantumState) -> complex:
        """Return ``<state|A|state>``; callers should use Hermitian A for observables."""
        result = self.apply_amplitudes(state.amplitudes)
        return sum(a.conjugate() * b for a, b in zip(state.amplitudes, result))
