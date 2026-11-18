"""Quotient-geometry audit fixture (NOT production) [REVIEW FIX R1].

The lane-0 projection p(x, y) = 219x + 98y (mod 256) is 256-to-1 and lossy. It is kept here only to
audit the fiber geometry; production gl2_transform.py folds and never truncates.
"""
from __future__ import annotations

from typing import Iterator

from chronus.kernels.gl2_transform import MASK, MODULUS, fold  # noqa: E402

INV_219_MOD256: int = pow(219, -1, MODULUS)  # [REVIEW FIX R3] = 83 (original comment said 59; 59*219 = 121 mod 256)
assert INV_219_MOD256 == 83


def fold_truncated(raw: bytes) -> bytes:
    """2:1 LOSSY projection keeping only lane 0 of each folded pair (odd tail padded with 0)."""
    data = fold(raw).data
    return bytes(data[0::2])


def trunc_fiber(u: int) -> Iterator[tuple[int, int]]:
    """The exact 256-element fiber {(x, y) : 219x + 98y = u (mod 256)} = {(83u - 98t, 219t)}."""
    if isinstance(u, bool) or not isinstance(u, int) or not (0 <= u < MODULUS):
        raise ValueError(f"u must be an integer in [0, 255], got {u!r}")
    x0 = (u * INV_219_MOD256) & MASK
    for t in range(MODULUS):
        yield ((x0 - 98 * t) & MASK, (219 * t) & MASK)


def test_quotient_fiber_exact_256_partition() -> None:
    seen: set[tuple[int, int]] = set()
    for u in range(256):
        fib = list(trunc_fiber(u))
        assert len(fib) == 256 and len(set(fib)) == 256
        for x, y in fib:
            assert fold_truncated(bytes((x, y))) == bytes((u,))
        seen.update(fib)
    assert len(seen) == 65536


def test_fold_truncated_matches_original_odd_tail() -> None:
    for x in range(256):
        assert fold_truncated(bytes((x,))) == bytes(((219 * x) & MASK,))
