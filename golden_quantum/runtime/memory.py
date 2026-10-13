"""
Memory allocation with prime-gap indexing and Lucas-scaled capacity.

The HYBA infrastructure pseudocode used prime gaps as allocation slots
with a capacity check. The original code had a critical bug:

    BUG: capacity = gap²  →  gap=5, size=10 passes (25 >= 10)
    BUT offset = gap - size = -5  →  buffer underflow

The corrected invariant is: allocation allowed only when gap >= size.
This ensures the offset (gap - size) is always non-negative.

Additionally, the Lucas-scaled allocation uses L(k) as a size threshold:
allocations of size <= L(k) can use a gap of index k.
"""

from ..sequences import lucas


def prime_gap(k: int) -> int:
    """The k-th prime gap: g_k = p_{k+1} - p_k.

    Uses a simple sieve. For the framework we only need small primes.
    """
    # Known small primes and their gaps
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53,
              59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113,
              127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181,
              191, 193, 197, 199, 211, 223, 227, 229, 233, 239, 241, 251]

    if k < 0 or k >= len(primes) - 1:
        # Fall back to computing for larger k
        if k < 0:
            raise ValueError("k must be non-negative")
        # Extend primes as needed
        p = primes[-1]
        while len(primes) <= k + 1:
            p = _next_prime(p)
            primes.append(p)

    return primes[k + 1] - primes[k]


def _next_prime(n: int) -> int:
    """Find the next prime after n."""
    candidate = n + 1
    while True:
        if _is_prime(candidate):
            return candidate
        candidate += 1


def _is_prime(n: int) -> bool:
    """Simple primality test."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def allocate_buggy(gap: int, size: int) -> tuple[bool, int]:
    """Original buggy allocation: accepts when gap² >= size.

    This allows gap=5, size=10 (25 >= 10) but produces offset = -5.
    Returns (accepted, offset).
    """
    capacity = gap * gap
    if capacity >= size:
        offset = gap - size  # BUG: can be negative!
        return (True, offset)
    return (False, 0)


def allocate_correct(gap: int, size: int) -> tuple[bool, int]:
    """Corrected allocation: accepts only when gap >= size.

    This ensures offset = gap - size >= 0 (no underflow).
    Returns (accepted, offset).
    """
    if gap >= size:
        offset = gap - size
        return (True, offset)
    return (False, 0)


def lucas_threshold(k: int) -> int:
    """Lucas-scaled allocation threshold: L(k).

    Allocations of size <= L(k) can use a gap of index k.
    """
    return int(lucas(k))


def allocate_lucas(k: int, size: int) -> tuple[bool, int]:
    """Lucas-scaled allocation: accepts when L(k) >= size.

    This combines the corrected invariant with Lucas scaling.
    Returns (accepted, offset) where offset = L(k) - size >= 0.
    """
    threshold = lucas_threshold(k)
    if threshold >= size:
        return (True, threshold - size)
    return (False, 0)
