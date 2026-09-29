"""Rigorous Cassini-Hoggatt invariant verification.

L_n^2 - 5 F_n^2 = 4 (-1)^n
"""


class CassiniVerifier:
    """Rigorous Cassini-Hoggatt invariant verification."""

    @staticmethod
    def lucas(n: int) -> int:
        if n == 0:
            return 2
        if n == 1:
            return 1
        a, b = 2, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @staticmethod
    def fibonacci(n: int) -> int:
        if n == 0:
            return 0
        if n == 1:
            return 1
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @classmethod
    def verify(cls, n: int) -> bool:
        """Verify the Cassini identity L_n^2 - 5 F_n^2 = 4 (-1)^n at index ``n``.

        This recomputes ``lucas(n)``/``fibonacci(n)`` and checks the identity
        on them — it is a theorem check on the arithmetic, not an admission
        gate. It returns True for every ``n`` the engine can compute, so
        gating caller-supplied values on it admits everything. To check a
        stored value, use :meth:`verify_with_values` /
        :meth:`verify_matrix`, or ``aethel.fibonacci.cassini_holds`` on the
        stored quadruple.
        """
        l_n = cls.lucas(n)
        f_n = cls.fibonacci(n)
        cassini_det = (l_n**2) - 5 * (f_n**2)
        expected = 4 * ((-1) ** n)
        return cassini_det == expected

    @classmethod
    def verify_identity(cls, n: int) -> bool:
        """Alias for verify() — the exact Cassini identity check."""
        return cls.verify(n)

    @classmethod
    def verify_with_values(cls, n: int, l_val: int, f_val: int) -> bool:
        """Verify with precomputed values."""
        cassini_det = (l_val**2) - 5 * (f_val**2)
        expected = 4 * ((-1) ** n)
        return cassini_det == expected

    @classmethod
    def verify_matrix(cls, n: int) -> bool:
        """Verify det(Q^n) = (-1)^n for the Cassini matrix Q."""
        # Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]
        f_np1 = cls.fibonacci(n + 1)
        f_n = cls.fibonacci(n)
        f_nm1 = cls.fibonacci(n - 1) if n > 0 else 1
        det = f_np1 * f_nm1 - f_n * f_n
        expected = (-1) ** n
        return det == expected
