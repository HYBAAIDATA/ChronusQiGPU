"""GoldenArithmetic — the exact integer arithmetic the millennium bridge cites.

This is the module the bridge imports. Delete it and the bridge stops importing.
It wraps the same Fibonacci/Lucas doubling used elsewhere in Chronus; it does
not introduce a second arithmetic.
"""

from __future__ import annotations

from chronus.security.al_haras.golden import fibonacci, lucas


class GoldenArithmetic:
    """Exact integer Fibonacci / Lucas / Cassini used by the bridge readings."""

    @staticmethod
    def fibonacci(n: int) -> int:
        return fibonacci(n)

    @staticmethod
    def lucas(n: int) -> int:
        return lucas(n)

    @staticmethod
    def cassini(n: int) -> int:
        """Return (-1)^n after checking F_{n+1} F_{n-1} - F_n^2 = (-1)^n.

        For n = 0 the identity is read as F_1 F_{-1} - F_0^2 with the usual
        extension F_{-1} = 1, which equals +1 = (-1)^0.
        """
        if n < 0:
            raise ValueError("Cassini index must be non-negative")
        if n == 0:
            # F_1 * F_{-1} - F_0^2 = 1 * 1 - 0 = 1
            return 1
        f_nm1 = fibonacci(n - 1)
        f_n = fibonacci(n)
        f_np1 = fibonacci(n + 1)
        value = f_np1 * f_nm1 - f_n * f_n
        expected = -1 if (n % 2) else 1
        if value != expected:
            raise AssertionError(
                f"Cassini failed at n={n}: got {value}, expected {expected}"
            )
        return expected
