"""Exact Walsh-Hadamard transforms.

H^(tensor n) has entries (-1)^(x.y) / 2^(n/2). The algorithms here apply it twice
around a phase oracle, so every amplitude carries the exact rational factor
1/2^n; the integer transform below is unnormalised and the normalisation is
applied with fractions.Fraction (zero rounding).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence, Union

__all__ = [
    "dot_parity",
    "inverse_walsh_hadamard",
    "phase_oracle_amplitudes",
    "walsh_hadamard",
]

Number = Union[int, Fraction]


def dot_parity(x: int, y: int) -> int:
    """x.y over GF(2): the parity of popcount(x & y)."""
    return (x & y).bit_count() & 1


def _length_exponent(length: int) -> int:
    n = length.bit_length() - 1
    if length < 1 or 1 << n != length:
        raise ValueError(f"length {length} is not a power of two")
    return n


def walsh_hadamard(values: Sequence[Number]) -> list[Number]:
    """Unnormalised transform: out[y] = sum_x (-1)^(x.y) values[x] (exact butterflies)."""
    data = list(values)
    for value in data:
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
            raise TypeError(f"Walsh-Hadamard entries must be ints or Fractions, got {value!r}")
    _length_exponent(len(data))
    half = 1
    size = len(data)
    while half < size:
        for start in range(0, size, 2 * half):
            for i in range(start, start + half):
                u = data[i]
                v = data[i + half]
                data[i] = u + v
                data[i + half] = u - v
        half *= 2
    return data


def inverse_walsh_hadamard(values: Sequence[Number]) -> list[Fraction]:
    """Inverse transform: (1/2^n) * walsh_hadamard(values), exact."""
    size = len(values)
    _length_exponent(size)
    return [Fraction(v) / size for v in walsh_hadamard(values)]


def phase_oracle_amplitudes(table: Sequence[int]) -> tuple[Fraction, ...]:
    """Amplitudes of H^n Z_f H^n |0^n>: entry y equals (1/2^n) sum_x (-1)^(f(x) + x.y)."""
    size = len(table)
    _length_exponent(size)
    signs = []
    for x, bit in enumerate(table):
        if bit not in (0, 1) or isinstance(bit, bool):
            raise ValueError(f"phase oracle value at x = {x} must be 0 or 1, got {bit!r}")
        signs.append(1 - 2 * bit)
    return tuple(Fraction(v, size) for v in walsh_hadamard(signs))
