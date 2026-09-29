"""Prime algebraic addressing — locating an object, with an honest boundary.

    Primes locate. Fibonacci represents. Zeckendorf encodes. Cassini
    verifies. Lucas scales. Pisot folds.

THE BOUNDARY, stated once and enforced
--------------------------------------
Prime addressing is a LOCATION scheme. It is NOT a physical capacity gain
and NOT a compression claim. Nothing in this module reduces bytes, and any
statement that it does is false.

A measured fact worth recording: in the existing repository the
Zeckendorf prime-bucket resolver was measured to be MANY-TO-ONE -- 1060
physical slots against 100000 logical indices, up to 317 entities per slot.
So a prime-derived slot is emphatically NOT a unique identity, and this
module refuses to pretend otherwise. Uniqueness is established by the store
layer, never by the address.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .fibonacci_store import fib, lucas
from .zeckendorf_codec import to_mask

__all__ = [
    "PrimeRecord",
    "prime_at",
    "prime_index_of",
    "prime_gap",
    "build_record",
    "PrimeAddressCollision",
    "address_capacity_boundary",
]


class PrimeAddressCollision(RuntimeError):
    """Two distinct logical indices resolved to one physical address."""


def _primes_upto(limit: int) -> List[int]:
    """Exact sieve of Eratosthenes. Integer arithmetic only."""
    if limit < 2:
        return []
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    p = 2
    while p * p <= limit:
        if sieve[p]:
            for q in range(p * p, limit + 1, p):
                sieve[q] = False
        p += 1
    return [i for i in range(limit + 1) if sieve[i]]


_PRIME_CACHE: Dict[int, List[int]] = {}


def prime_at(index: int, limit: int = 100_000) -> int:
    """The ``index``-th prime (0-based), exact integer."""
    if index < 0:
        raise ValueError("prime index must be non-negative")
    if limit not in _PRIME_CACHE:
        _PRIME_CACHE[limit] = _primes_upto(limit)
    primes = _PRIME_CACHE[limit]
    if index >= len(primes):
        raise ValueError(f"prime index {index} exceeds limit {limit}")
    return primes[index]


def prime_index_of(prime: int, limit: int = 100_000) -> int:
    """Inverse of :func:`prime_at`."""
    if limit not in _PRIME_CACHE:
        _PRIME_CACHE[limit] = _primes_upto(limit)
    primes = _PRIME_CACHE[limit]
    if prime not in primes:
        raise ValueError(f"{prime} is not prime within limit {limit}")
    return primes.index(prime)


def prime_gap(index: int) -> int:
    """``p_{k+1} - p_k``. Exact integer."""
    return prime_at(index + 1) - prime_at(index)


@dataclass(frozen=True)
class PrimeRecord:
    """The address-and-proof record for one logical object."""

    object_id: str
    index: int
    prime_id: int
    prime_index: int
    prime_gap: int
    zeckendorf_index: int
    zeckendorf_mask: int
    fibonacci_state: tuple
    lucas_scale: int
    cassini_seal: int
    payload: bytes
    lossless: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "index": self.index,
            "prime_id": self.prime_id,
            "prime_index": self.prime_index,
            "prime_gap": self.prime_gap,
            "zeckendorf_index": self.zeckendorf_index,
            "fibonacci_state": list(self.fibonacci_state),
            "lucas_scale": self.lucas_scale,
            "cassini_seal": self.cassini_seal,
            "lossless": self.lossless,
            "payload_bytes": len(self.payload),
        }


def build_record(
    object_id: str,
    index: int,
    payload: bytes,
    *,
    scale: int = 15,
    lossless: bool = True,
) -> PrimeRecord:
    """Build the prime-addressed record, attaching the exact proof state."""
    if index < 0:
        raise ValueError("index must be non-negative")
    from .cassini import verify_state

    proofs = verify_state(index)
    proven = all(p.passed for p in proofs)
    seal = proofs[0].expected if proofs else 0
    return PrimeRecord(
        object_id=object_id,
        index=index,
        prime_id=prime_at(index),
        prime_index=index,
        prime_gap=prime_gap(index),
        zeckendorf_index=index,
        zeckendorf_mask=to_mask(index),
        fibonacci_state=(fib(index), fib(index + 1)),
        lucas_scale=lucas(scale),
        cassini_seal=seal,
        payload=payload,
        lossless=lossless and proven,
    )


def address_capacity_boundary() -> Dict[str, Any]:
    """State plainly what prime addressing does and does not do.

    This exists so the distinction travels with the code rather than living
    only in a document, where it can be lost in a rewrite.
    """
    return {
        "addressing_gain": "PRIMES LOCATE. A prime address is a location scheme.",
        "representation_gain": "FIBONACCI REPRESENTS. Exact recurrence state, not floats.",
        "physical_capacity_gain": "NOT CLAIMED. Prime addressing adds no physical bytes.",
        "injectivity": (
            "NOT AN IDENTITY. A prime-derived slot is many-to-one; uniqueness "
            "is established by the store layer, never by the address."
        ),
    }
