"""Carmichael primitive-divisor addressing (internal mathematics).

An index n > 12 maps to the smallest prime that divides F(n) and no earlier
F(m). That prime is a unique address under Carmichael's theorem for n > 12.

This module is **not** a customer-visible surface. Public APIs must not
re-export these names; the procurement / tier layer is the public vocabulary.
"""

from __future__ import annotations


def fib(n: int) -> int:
    if n < 0:
        raise ValueError("fibonacci index must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def factors(n: int) -> set[int]:
    if n <= 0:
        raise ValueError("factors require a positive integer")
    out: set[int] = set()
    d = 2
    while d * d <= n:
        while n % d == 0:
            out.add(d)
            n //= d
        d += 1
    if n > 1:
        out.add(n)
    return out


def primitive_divisor(n: int) -> int | None:
    """Smallest prime dividing F(n) and no earlier F(m). None if there is none.

    Carmichael: one exists for every n > 12, so an index is a unique address.
    """
    if n < 3:
        return None
    fresh = factors(fib(n))
    for m in range(3, n):
        fresh -= factors(fib(m))
        if not fresh:
            return None
    return min(fresh) if fresh else None


def address_of(n: int) -> int:
    """Prime address for index n. Raises below the theorem's floor."""
    if n <= 12:
        raise ValueError(
            f"index {n} is below Carmichael's floor; no primitive divisor"
        )
    prime = primitive_divisor(n)
    if prime is None:
        raise AssertionError(f"Carmichael violated at {n}")
    return prime


def self_test(*, unique_through: int = 80) -> None:
    """Existence through 59; uniqueness through ``unique_through`` (CI default 80).

    A full Carmichael sweep to 300 is valid but factoring F(n) for large n is
    expensive; keep that as an explicit opt-in (``unique_through=300``).
    """
    if unique_through <= 12:
        raise ValueError("unique_through must exceed Carmichael's floor")
    for n in range(13, 60):
        assert primitive_divisor(n) is not None, f"no primitive divisor at {n}"
    seen: dict[int, int] = {}
    for n in range(13, unique_through + 1):
        p = address_of(n)
        assert p not in seen, f"address collision: {n} and {seen[p]} share {p}"
        seen[p] = n
    assert primitive_divisor(12) is None  # 144 = 2^4 * 3^2, both earlier
    assert primitive_divisor(13) == 233


if __name__ == "__main__":
    self_test()
    print("carmichael address self-test passed")
