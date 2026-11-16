"""Bounded reversible prime-product label address, not a physical disk address.

This is the reference logical indexing primitive from the Notion/benchmark
research. It cannot correct corruption and makes no p-adic, persistence,
throughput, or storage capacity claim.
"""
from __future__ import annotations

from functools import lru_cache

LABEL_DOMAIN = 4096
MAX_LABELS = 32


@lru_cache(maxsize=1)
def _primes() -> tuple[int, ...]:
    result: list[int] = []
    candidate = 2
    while len(result) < LABEL_DOMAIN:
        prime = True
        for p in result:
            if p * p > candidate:
                break
            if candidate % p == 0:
                prime = False
                break
        if prime:
            result.append(candidate)
        candidate += 1
    return tuple(result)


def encode_labels(labels: list[int] | tuple[int, ...]) -> int:
    """Prime product of a label *set*: unique and independent of input order."""
    if not isinstance(labels, (list, tuple)) or len(labels) > MAX_LABELS:
        raise ValueError("labels must be a bounded list or tuple")
    if any(not isinstance(i, int) or isinstance(i, bool) or
           i < 0 or i >= LABEL_DOMAIN for i in labels):
        raise ValueError("label outside the supported domain")
    if len(set(labels)) != len(labels):
        raise ValueError("duplicate labels are not permitted")
    primes = _primes()
    result = 1
    for i in labels:
        result *= primes[i]
    return result


def decode_labels(address: int) -> tuple[int, ...]:
    """Factor only against the specified domain; reject invalid addresses."""
    if not isinstance(address, int) or isinstance(address, bool) or address < 1:
        raise ValueError("address must be a positive integer")
    remaining = address
    labels: list[int] = []
    for i, p in enumerate(_primes()):
        if remaining % p == 0:
            remaining //= p
            if remaining % p == 0:
                raise ValueError("repeated prime factor")
            labels.append(i)
            if len(labels) > MAX_LABELS:
                raise ValueError("too many labels")
        if remaining == 1:
            break
    if remaining != 1:
        raise ValueError("unknown prime factor")
    return tuple(labels)


def packed_address_bytes(address: int) -> int:
    """Only integer-address bytes; not the complete database or payload."""
    decode_labels(address)
    return max(1, (address.bit_length() + 7) // 8)
