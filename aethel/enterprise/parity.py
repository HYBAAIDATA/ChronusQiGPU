"""CPU vs Chronus-accel digest parity helpers.

Chronus may accelerate but must not change content digests.
"""
from __future__ import annotations

from typing import Callable, Optional

from .authenticity import content_digest
from .errors import AuthorityBoundaryError


def assert_cpu_accel_parity(
    payload: bytes,
    *,
    cpu_path: Optional[Callable[[bytes], bytes]] = None,
    accel_path: Optional[Callable[[bytes], bytes]] = None,
) -> str:
    """Return shared digest; raise AuthorityBoundaryError on mismatch.

    Default paths are identity (custody stores raw/folded bytes identically
    whether chronus_accel flag is on or off). Callers may inject encode hooks.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    payload = bytes(payload)
    cpu_fn = cpu_path or (lambda b: b)
    accel_fn = accel_path or (lambda b: b)
    cpu_out = cpu_fn(payload)
    accel_out = accel_fn(payload)
    d_cpu = content_digest(cpu_out)
    d_accel = content_digest(accel_out)
    if d_cpu != d_accel:
        raise AuthorityBoundaryError(
            "Chronus accel path changed digest — forbidden by authority matrix"
        )
    return d_cpu


__all__ = ["assert_cpu_accel_parity"]
