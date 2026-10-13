"""Exact Cassini identity for Lucas/Fibonacci numbers.

L_n^2 - 5*F_n^2 = 4*(-1)^n
"""

from __future__ import annotations

from .core import fibonacci, lucas


def cassini(n: int) -> dict[str, object]:
    """Return Cassini-Lucas identity witness for index n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    L_n = lucas(n)
    F_n = fibonacci(n)
    lhs = L_n * L_n - 5 * F_n * F_n
    rhs = 4 * (-1 if n % 2 else 1)
    return {
        "n": n,
        "L_n": L_n,
        "F_n": F_n,
        "lhs": lhs,
        "rhs": rhs,
        "valid": lhs == rhs,
    }


def cassini_range(max_n: int) -> list[dict[str, object]]:
    """Witness Cassini-Lucas for n = 0..max_n."""
    return [cassini(n) for n in range(max_n + 1)]


def verify(n: int) -> dict[str, object]:
    """Verify L_n^2 - 5*F_n^2 = 4*(-1)^n exactly for index n."""
    witness = cassini(n)
    witness["theorem_proven"] = False
    return witness


def verify_range(max_n: int = 20) -> bool:
    """True iff the Cassini-Lucas identity holds for every n = 0..max_n."""
    return all(cassini(n)["valid"] for n in range(max_n + 1))
