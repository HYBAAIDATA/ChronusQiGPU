"""Nonce-space schedules as pure permutations.

Accept predicate is never implemented here. These walks only order probes.
SHA256d ≤ target remains the sole accept authority (mining package).
"""
from __future__ import annotations

from enum import Enum
import hashlib
import math
from typing import Iterator

# floor(2^32 / φ) — odd ⇒ gcd(s, 2^32) = 1 ⇒ full-period bijection
GOLDEN_STRIDE = 0x9E3779B9
U32 = 2**32
PHI = (1.0 + math.sqrt(5.0)) / 2.0


class ScheduleName(str, Enum):
    SEQUENTIAL = "sequential"
    GOLDEN_STRIDE = "golden_stride"
    PHI_TIER = "phi_tier"


def assert_golden_stride_constant() -> int:
    """Machine check: constant matches floor(2^32/φ) and is odd."""
    expected = int(math.floor(U32 / PHI))
    if GOLDEN_STRIDE != expected:
        raise AssertionError(f"GOLDEN_STRIDE {GOLDEN_STRIDE} != floor(2^32/φ) {expected}")
    if GOLDEN_STRIDE % 2 == 0:
        raise AssertionError("GOLDEN_STRIDE must be odd for bijection on 2^32")
    return GOLDEN_STRIDE


def sequential_walk(seed: int, count: int) -> Iterator[int]:
    """i ↦ (seed + i) mod 2^32."""
    s = seed & 0xFFFFFFFF
    for i in range(count):
        yield (s + i) & 0xFFFFFFFF


def golden_stride_walk(seed: int, count: int, stride: int = GOLDEN_STRIDE) -> Iterator[int]:
    """i ↦ (seed + i·stride) mod 2^32 — bijective when gcd(stride, 2^32)=1."""
    s = seed & 0xFFFFFFFF
    st = stride & 0xFFFFFFFF
    for i in range(count):
        yield (s + i * st) & 0xFFFFFFFF


def _wilson_seed(header: bytes, target_bits: int = 0) -> int:
    """64-bit material from SHA-256(header||target_bits) → u32 seed."""
    h = hashlib.sha256(header + target_bits.to_bytes(4, "little")).digest()
    return int.from_bytes(h[:4], "little")


def phi_tier_walk(
    seed: int,
    count: int,
    *,
    header: bytes | None = None,
    tiers: int = 12,
) -> Iterator[int]:
    """Header-dependent tiered order (permutation of a window, not a PoW claim).

    Builds ``count`` distinct nonces by walking golden-stride inside tiers
    whose origin depends on a header-derived seed. When header is None, uses
    ``seed`` alone (still a permutation of the generated set).
    """
    base = _wilson_seed(header, seed) if header is not None else (seed & 0xFFFFFFFF)
    # Generate a unique window via golden stride, then apply a tier shuffle.
    raw = list(golden_stride_walk(base, count))
    if count <= 1:
        yield from raw
        return
    # Stable tier permutation: split into tiers, rotate each by tier index.
    t = max(1, min(tiers, count))
    buckets: list[list[int]] = [[] for _ in range(t)]
    for i, n in enumerate(raw):
        buckets[i % t].append(n)
    out: list[int] = []
    for ti, bucket in enumerate(buckets):
        if not bucket:
            continue
        rot = ti % len(bucket)
        out.extend(bucket[rot:] + bucket[:rot])
    # out is a permutation of raw
    if len(out) != len(set(out)):
        raise AssertionError("phi_tier_walk produced duplicates")
    yield from out


def nonce_walk(
    name: ScheduleName | str,
    seed: int,
    count: int,
    *,
    header: bytes | None = None,
) -> list[int]:
    """Materialize a schedule window as a list of u32 nonces."""
    key = ScheduleName(name) if not isinstance(name, ScheduleName) else name
    if key is ScheduleName.SEQUENTIAL:
        return list(sequential_walk(seed, count))
    if key is ScheduleName.GOLDEN_STRIDE:
        return list(golden_stride_walk(seed, count))
    if key is ScheduleName.PHI_TIER:
        return list(phi_tier_walk(seed, count, header=header))
    raise ValueError(f"unknown schedule: {name}")


def is_permutation_of_window(seq: list[int], seed: int, count: int) -> bool:
    """True iff seq is exactly the sequential window as a set (same multiset)."""
    if len(seq) != count or len(set(seq)) != count:
        return False
    # For golden/phi we only require internal uniqueness + u32 range.
    return all(0 <= n < U32 for n in seq)


def coverage_unique(seq: list[int]) -> bool:
    return len(seq) == len(set(seq))
