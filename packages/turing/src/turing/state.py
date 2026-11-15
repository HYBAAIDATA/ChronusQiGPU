"""Normalized finite-dimensional state vectors over the complex numbers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

DEFAULT_TOLERANCE = 1e-10


def _as_finite_complex(value: complex | float | int) -> complex:
    result = complex(value)
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError("amplitudes must be finite complex numbers")
    return result


@dataclass(frozen=True, slots=True)
class QuantumState:
    """A normalized ket in a finite-dimensional complex Hilbert space.

    The constructor rejects zero or non-normalized vectors. Use
    :meth:`normalized` when explicit normalization is intended.
    """

    amplitudes: tuple[complex, ...]

    def __post_init__(self) -> None:
        values = tuple(_as_finite_complex(value) for value in self.amplitudes)
        if not values:
            raise ValueError("a state must have at least one amplitude")
        norm_squared = sum(abs(value) ** 2 for value in values)
        if not math.isclose(norm_squared, 1.0, rel_tol=0.0, abs_tol=DEFAULT_TOLERANCE):
            raise ValueError(f"state must be normalized; squared norm is {norm_squared!r}")
        object.__setattr__(self, "amplitudes", values)

    @classmethod
    def basis(cls, dimension: int, index: int) -> "QuantumState":
        """Return the computational basis ket ``|index>`` in ``C^dimension``."""
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
            raise ValueError("dimension must be a positive integer")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < dimension:
            raise ValueError("basis index must be in range")
        return cls(tuple(1.0 + 0.0j if i == index else 0.0j for i in range(dimension)))

    @classmethod
    def normalized(cls, amplitudes: Iterable[complex | float | int]) -> "QuantumState":
        """Explicitly normalize a nonzero amplitude sequence into a state."""
        values = tuple(_as_finite_complex(value) for value in amplitudes)
        if not values:
            raise ValueError("a state must have at least one amplitude")
        norm = math.sqrt(sum(abs(value) ** 2 for value in values))
        if norm == 0.0:
            raise ValueError("the zero vector cannot be normalized")
        return cls(tuple(value / norm for value in values))

    @property
    def dimension(self) -> int:
        return len(self.amplitudes)

    @property
    def norm_squared(self) -> float:
        return sum(abs(value) ** 2 for value in self.amplitudes)

    def inner_product(self, other: "QuantumState") -> complex:
        """Return ``<self|other>`` (conjugate-linear in the first argument)."""
        if not isinstance(other, QuantumState):
            raise TypeError("other must be a QuantumState")
        if self.dimension != other.dimension:
            raise ValueError("state dimensions must match")
        return sum(a.conjugate() * b for a, b in zip(self.amplitudes, other.amplitudes))
