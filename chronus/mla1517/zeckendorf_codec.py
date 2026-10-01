"""Zeckendorf codec — encode/decode an integer index or mask.

Canonical form: the unique sum of NON-ADJACENT Fibonacci numbers. A mask
bit ``i`` set means ``F_{i+2}`` participates, which is the convention the
D5 Zeckendorf field uses in the 64-byte descriptor.

The codec enforces the non-adjacency rule on encode, so it can never emit a
representation that decodes ambiguously.
"""

from __future__ import annotations

from .fibonacci_store import fib, zeckendorf_indices

__all__ = [
    "ZeckendorfError",
    "encode",
    "decode",
    "to_mask",
    "from_mask",
    "is_valid_mask",
    "mask_popcount",
]


class ZeckendorfError(ValueError):
    """A Zeckendorf encoding or mask violated the canonical form."""


def encode(value: int) -> list[int]:
    """Canonical non-adjacent Fibonacci indices summing to ``value``."""
    return zeckendorf_indices(value)


def decode(indices: list[int]) -> int:
    """Value whose Zeckendorf representation is ``indices``."""
    from .fibonacci_store import fib_from_zeckendorf

    return fib_from_zeckendorf(indices)


def to_mask(value: int) -> int:
    """Pack a Zeckendorf decomposition into a uint32 mask.

    Bit ``i`` corresponds to ``F_{i+2}``, so the mask stays inside uint32
    for the practical index range and matches the D5 field width.
    """
    if value < 0:
        raise ZeckendorfError("value must be non-negative")
    mask = 0
    for k in encode(value):
        bit = k - 2
        if bit < 0:
            raise ZeckendorfError(f"index {k} does not fit the mask encoding")
        if bit > 31:
            raise ZeckendorfError("index too large for a uint32 mask")
        mask |= 1 << bit
    return mask


def from_mask(mask: int) -> int:
    """Unpack a uint32 Zeckendorf mask back to its value.

    Rejects adjacent set bits rather than silently normalising them: a
    corrupted mask must be visible, not quietly repaired.
    """
    if mask < 0:
        raise ZeckendorfError("mask must be non-negative")
    if mask & (mask << 1):
        raise ZeckendorfError("mask has adjacent set bits: not canonical")
    value = 0
    for bit in range(32):
        if mask & (1 << bit):
            value += fib(bit + 2)
    return value


def is_valid_mask(mask: int) -> bool:
    """True when the mask is canonical (no adjacent set bits)."""
    return mask >= 0 and not (mask & (mask << 1))


def mask_popcount(mask: int) -> int:
    """Number of Fibonacci terms in the representation."""
    return bin(mask).count("1")
