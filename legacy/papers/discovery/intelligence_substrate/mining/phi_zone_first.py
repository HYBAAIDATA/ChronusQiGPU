"""
Phyllotaxis Sunflower Nonce Ordering & Phi-Zone Iterator
========================================================
Module: mining/phi_zone_first.py

Generates nonces in golden-angle spiral order (theta = n * 2.39996323 rad)
partitioning and prioritizing the phi-resonance zone over sequential scans.
"""

from __future__ import annotations
from typing import Iterator, Optional

try:
    from pythagoras.constants import GOLDEN_NONCE_STRIDE, GOLDEN_ANGLE_RAD
except ImportError:
    GOLDEN_NONCE_STRIDE = 2654435769
    GOLDEN_ANGLE_RAD = 2.399963229728653


def phi_zone_first(
    limit: Optional[int] = None,
    base: int = 0,
    stride: int = GOLDEN_NONCE_STRIDE,
) -> Iterator[int]:
    """
    Yields nonces according to the phyllotaxis golden angle Weyl progression:
        nonce_n = (base + n * stride) mod 2^32

    Since gcd(stride, 2^32) == 1, this sequence generates a full-period,
    bijective low-discrepancy traversal of the 32-bit nonce space.
    """
    count = 0
    n = 0
    while True:
        if limit is not None and count >= limit:
            break
        nonce = (base + n * stride) & 0xFFFFFFFF
        yield int(nonce)
        count += 1
        n += 1


if __name__ == "__main__":
    print(list(phi_zone_first(10))[:10])
