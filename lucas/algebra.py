"""Exact Lucas algebra over the quadratic integer ring Z[phi].

This module is deliberately narrower than a quantum-category claim.  It
implements the algebra that is actually present:

    phi**2 = phi + 1
    conjugate(phi) = 1 - phi
    trace(phi**n) = L_n
    coefficient_of_phi(phi**n) = F_n

All values are arbitrary-precision integers.  No floating point, Binet
evaluation, sampling, or hardware assumption is used.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZPhi:
    """An exact element ``a + b*phi`` of the ring Z[phi]."""

    a: int = 0
    b: int = 0

    def __add__(self, other: "ZPhi") -> "ZPhi":
        if not isinstance(other, ZPhi):
            return NotImplemented
        return ZPhi(self.a + other.a, self.b + other.b)

    def __sub__(self, other: "ZPhi") -> "ZPhi":
        if not isinstance(other, ZPhi):
            return NotImplemented
        return ZPhi(self.a - other.a, self.b - other.b)

    def __neg__(self) -> "ZPhi":
        return ZPhi(-self.a, -self.b)

    def __mul__(self, other: "ZPhi") -> "ZPhi":
        if not isinstance(other, ZPhi):
            return NotImplemented
        return ZPhi(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
        )

    def __pow__(self, exponent: int) -> "ZPhi":
        if not isinstance(exponent, int):
            raise TypeError("exponent must be an integer")
        if exponent < 0:
            # phi is a unit: phi^{-1} = phi - 1.
            base = PHI - ONE
            exponent = -exponent
        else:
            base = self
        result = ONE
        while exponent:
            if exponent & 1:
                result = result * base
            base = base * base
            exponent >>= 1
        return result

    def conjugate(self) -> "ZPhi":
        """Apply the exact non-trivial automorphism phi -> 1 - phi."""
        return ZPhi(self.a + self.b, -self.b)

    def trace(self) -> int:
        return self.a + self.conjugate().a

    def norm(self) -> int:
        product = self * self.conjugate()
        if product.b != 0:
            raise ArithmeticError("Z[phi] norm did not reduce to an integer")
        return product.a

    def multiplication_matrix(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Matrix of left multiplication in the basis (1, phi)."""
        return ((self.a, self.b), (self.b, self.a + self.b))


ZERO = ZPhi(0, 0)
ONE = ZPhi(1, 0)
PHI = ZPhi(0, 1)


def phi_power(n: int) -> ZPhi:
    """Return the exact ring element phi**n for any integer n."""
    if not isinstance(n, int):
        raise TypeError("Lucas index must be an integer")
    return PHI**n


def fibonacci(n: int) -> int:
    """Return F_n as the phi coefficient of phi**n."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Fibonacci index must be a non-negative integer")
    return phi_power(n).b


def lucas(n: int) -> int:
    """Return L_n as the exact trace of phi**n."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Lucas index must be a non-negative integer")
    return phi_power(n).trace()


def lucas_addition(a: int, b: int) -> int:
    """Compute L_(a+b) through the exact Lucas/Fibonacci composition law."""
    if not isinstance(a, int) or not isinstance(b, int) or a < 0 or b < 0:
        raise ValueError("Lucas indices must be non-negative integers")
    numerator = lucas(a) * lucas(b) + 5 * fibonacci(a) * fibonacci(b)
    if numerator % 2:
        raise ArithmeticError("Lucas addition numerator is not even")
    return numerator // 2


def lucas_subtraction(a: int, b: int) -> int:
    """Compute L_(a-b) for a >= b through the exact subtraction law."""
    if (
        not isinstance(a, int)
        or not isinstance(b, int)
        or a < 0
        or b < 0
        or a < b
    ):
        raise ValueError("require non-negative indices with a >= b")
    numerator = ((-1) ** b) * (
        lucas(a) * lucas(b) - 5 * fibonacci(a) * fibonacci(b)
    )
    if numerator % 2:
        raise ArithmeticError("Lucas subtraction numerator is not even")
    return numerator // 2


def lucas_matrix(n: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return the exact multiplication matrix of phi**n.

    Its trace is L_n and its determinant is (-1)^n.  This is an algebraic
    representation of the quadratic ring, not a claim about anyon braiding.
    """
    return phi_power(n).multiplication_matrix()


__all__ = [
    "ONE",
    "PHI",
    "ZERO",
    "ZPhi",
    "fibonacci",
    "lucas",
    "lucas_addition",
    "lucas_matrix",
    "lucas_subtraction",
    "phi_power",
]
