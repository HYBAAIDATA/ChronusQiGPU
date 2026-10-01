from __future__ import annotations
import hashlib
import json
import math
from functools import lru_cache


def fib_pair(n: int) -> tuple[int, int]:
    """Return (F_n, F_{n+1}) exactly using fast doubling."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if n == 0:
        return 0, 1
    a, b = fib_pair(n // 2)
    c = a * (2 * b - a)
    d = a * a + b * b
    return (d, c + d) if n & 1 else (c, d)


def fib(n: int) -> int:
    return fib_pair(n)[0]


def lucas(n: int) -> int:
    a, b = fib_pair(n)
    return 2 * b - a


def cassini(n: int) -> int:
    if n < 1:
        raise ValueError("Cassini is defined here for n >= 1")
    return fib(n - 1) * fib(n + 1) - fib(n) ** 2


@lru_cache(maxsize=4096)
def _fib_basis(limit: int) -> tuple[int, ...]:
    values = [1, 2]
    while values[-1] <= limit:
        values.append(values[-1] + values[-2])
    return tuple(values)


def zeckendorf(n: int) -> tuple[int, tuple[int, ...]]:
    """Return (bit-mask, descending Fibonacci indices) for n >= 0."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if n == 0:
        return 0, ()
    basis = _fib_basis(n)
    remainder, mask, indices = n, 0, []
    for i in range(len(basis) - 1, -1, -1):
        if basis[i] <= remainder:
            remainder -= basis[i]
            mask |= 1 << i
            indices.append(i)
    if remainder:
        raise ArithmeticError("Zeckendorf encoding left a remainder")
    return mask, tuple(indices)


def zeckendorf_decode(mask: int) -> int:
    if not isinstance(mask, int) or mask < 0:
        raise ValueError("mask must be a non-negative integer")
    basis = [1, 2]
    while (1 << (len(basis) - 1)) <= mask:
        basis.append(basis[-1] + basis[-2])
    return sum(basis[i] for i in range(len(basis)) if mask & (1 << i))


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def nth_prime(index: int) -> int:
    """1-indexed deterministic prime address; intended for logical addressing."""
    if not isinstance(index, int) or index < 1:
        raise ValueError("prime index must be >= 1")
    count, candidate = 0, 1
    while count < index:
        candidate += 1
        root = math.isqrt(candidate)
        if all(candidate % p for p in range(2, root + 1)):
            count += 1
    return candidate
