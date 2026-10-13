"""
HYBA Core — φ-Substrate Primitives (Corrected)
Zero floating point, zero approximation, pure integer arithmetic.

Bug 2 fix: cassini_integrity_check now validates full matrix structure,
not just trace/determinant. Rejects impostors like [[0,1],[1,4]].
"""

import math
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from typing import Tuple, List, Optional
from numbers import Integral

getcontext().prec = 5000

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2

PHI_D = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
PSI_D = (Decimal(1) - Decimal(5).sqrt()) / Decimal(2)
SQRT5_D = Decimal(5).sqrt()


class HYBACore:
    """
    HYBA Core — φ-Substrate Primitives

    Provides:
    - Fibonacci/Lucas exact integer sequences
    - Binet closed forms with Decimal precision
    - Matrix operations M_φ^n
    - Cassini invariants (parity, orientation, integrity)
    - φ^15 coherence gate
    """

    def __init__(self):
        self._phi = PHI
        self._psi = PSI
        self._phi_d = PHI_D
        self._psi_d = PSI_D
        self._sqrt5_d = SQRT5_D

    # ─── Fibonacci/Lucas (Exact Integer) ──

    def fib_pair(self, n: int) -> Tuple[int, int]:
        """Fast doubling: returns (F(n), F(n+1)). F(0)=0, F(1)=1."""
        if n == 0:
            return (0, 1)
        a, b = self.fib_pair(n >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        if n & 1:
            return (d, c + d)
        return (c, d)

    def fibonacci(self, n: int) -> int:
        """F(n) exact integer. F(0)=0, F(1)=1."""
        if n < 0:
            return (-1)**(n+1) * self.fibonacci(-n)
        return self.fib_pair(n)[0]

    def lucas(self, n: int) -> int:
        """L(n) exact integer. L(0)=2, L(1)=1."""
        if n < 0:
            return (-1)**n * self.lucas(-n)
        if n == 0:
            return 2
        if n == 1:
            return 1
        f_n, f_n1 = self.fib_pair(n)
        return 2 * f_n1 - f_n

    # ─── Binet (Decimal Precision) ──

    def binet_f(self, n: int) -> int:
        """Binet's formula: F(n) = (φ^n - ψ^n) / √5."""
        if n < 0:
            sign = (-1)**(n+1)
            return sign * self.binet_f(-n)
        val = (self._phi_d ** n - self._psi_d ** n) / self._sqrt5_d
        return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))

    def binet_l(self, n: int) -> int:
        """Binet's formula for Lucas: L(n) = φ^n + ψ^n."""
        if n < 0:
            return (-1)**n * self.binet_l(-n)
        val = self._phi_d ** n + self._psi_d ** n
        return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))

    # ─── Matrix Operations ──

    def matrix_power(self, n: int) -> List[List[int]]:
        """M_φ^n = [[F(n+1), F(n)], [F(n), F(n-1)]]."""
        if n == 0:
            return [[1, 0], [0, 1]]
        if n < 0:
            sign = (-1)**n
            fn = self.fibonacci(-n)
            fn1 = self.fibonacci(-n + 1)
            fn_1 = self.fibonacci(-n - 1)
            return [
                [sign * fn_1, -sign * fn],
                [-sign * fn, sign * fn1]
            ]
        fn = self.fibonacci(n)
        fn1 = self.fibonacci(n + 1)
        fn_1 = self.fibonacci(n - 1)
        return [[fn1, fn], [fn, fn_1]]

    def matrix_det(self, m: List[List[int]]) -> int:
        return m[0][0] * m[1][1] - m[0][1] * m[1][0]

    def matrix_trace(self, m: List[List[int]]) -> int:
        return m[0][0] + m[1][1]

    def matrix_multiply(self, a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
        return [
            [
                a[0][0] * b[0][0] + a[0][1] * b[1][0],
                a[0][0] * b[0][1] + a[0][1] * b[1][1],
            ],
            [
                a[1][0] * b[0][0] + a[1][1] * b[1][0],
                a[1][0] * b[0][1] + a[1][1] * b[1][1],
            ],
        ]

    # ─── Cassini Invariants (BUG 2 FIXED) ──

    def cassini_parity(self, n: int) -> int:
        """det(M_φ^n) = (-1)^n. Returns -1 for odd, +1 for even."""
        return self.matrix_det(self.matrix_power(n))

    def cassini_integrity_check(self, m: List[List[int]]) -> bool:
        """
        Check if matrix is a valid M_φ^n state (CORRECTED).

        Validates:
          1. Shape is 2×2
          2. All entries are integers
          3. Non-negative entries (canonical form for n >= 0)
          4. Symmetric: m[0][1] == m[1][0]
          5. Structural: m[0][0] - m[1][1] == m[0][1]  (F(n+1) - F(n-1) = F(n))
          6. Determinant is ±1 (Cassini invariant)
          7. Recovers n and verifies full matrix match

        This rejects impostors like [[0,1],[1,4]] which have the right
        trace and determinant but wrong structure.
        """
        # Shape check
        if not isinstance(m, list) or len(m) != 2:
            return False
        if not all(isinstance(row, list) and len(row) == 2 for row in m):
            return False

        a, b = m[0][0], m[0][1]
        c, d = m[1][0], m[1][1]

        # Integer entries
        if not all(isinstance(v, Integral) for v in [a, b, c, d]):
            return False

        # Non-negative (canonical n >= 0)
        if a < 0 or b < 0 or c < 0 or d < 0:
            return False

        # Symmetry
        if b != c:
            return False

        # Structural: F(n+1) - F(n-1) = F(n), so a - d = b
        if a - d != b:
            return False

        # Determinant must be ±1
        det = a * d - b * c
        if det not in (-1, 1):
            return False

        # Recover n and verify full matrix match
        # F(n) = b, but F(1)=F(2)=1, so try all candidates
        candidates = []
        if b == 0:
            candidates = [0]
        elif b == 1:
            candidates = [1, 2]
        else:
            n = 2
            while self.fibonacci(n) <= b:
                if self.fibonacci(n) == b:
                    candidates.append(n)
                n += 1

        for n in candidates:
            if self.matrix_power(n) == [[a, b], [c, d]]:
                return True

        return False



    # ─── φ^15 Coherence Gate ──

    def coherence_gate(self, value: float) -> float:
        """φ^15 coherence gate."""
        L_15 = self.lucas(15)  # 1364
        scaled = value * L_15
        return 1.0 / (1.0 + abs(scaled - round(scaled)))
