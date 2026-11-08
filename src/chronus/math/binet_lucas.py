"""
Chronus Binet Folds & Pisot-Lucas Exact Algebraic Field Engine.

Mathematical Contract:
----------------------
Binet's formula involves sqrt(5), which is irrational. To achieve 100% exact,
lossless rational folding over Q(sqrt(5)) without floating-point precision decay,
elements are represented strictly as pairs (a, b) in Q^2, representing:
a + b * sqrt(5)

Operations:
-----------
- Addition:      (a1 + b1*sqrt(5)) + (a2 + b2*sqrt(5)) = (a1+a2) + (b1+b2)*sqrt(5)
- Multiplication:(a1 + b1*sqrt(5)) * (a2 + b2*sqrt(5)) = (a1*a2 + 5*b1*b2) + (a1*b2 + a2*b1)*sqrt(5)
- Inversion:     1 / (a + b*sqrt(5)) = (a - b*sqrt(5)) / (a^2 - 5*b^2)
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Tuple


@dataclass(frozen=True)
class QSqrt5:
    """Exact element of Q(sqrt(5)) represented as a + b*sqrt(5) using exact Fractions."""
    a: Fraction
    b: Fraction

    def __post_init__(self):
        if not isinstance(self.a, Fraction):
            object.__setattr__(self, "a", Fraction(self.a))
        if not isinstance(self.b, Fraction):
            object.__setattr__(self, "b", Fraction(self.b))

    def __add__(self, other: "QSqrt5") -> "QSqrt5":
        return QSqrt5(self.a + other.a, self.b + other.b)

    def __sub__(self, other: "QSqrt5") -> "QSqrt5":
        return QSqrt5(self.a - other.a, self.b - other.b)

    def __mul__(self, other: "QSqrt5") -> "QSqrt5":
        # (a1 + b1*sqrt(5)) * (a2 + b2*sqrt(5)) = (a1*a2 + 5*b1*b2) + (a1*b2 + a2*b1)*sqrt(5)
        new_a = self.a * other.a + Fraction(5) * self.b * other.b
        new_b = self.a * other.b + self.b * other.a
        return QSqrt5(new_a, new_b)

    def __neg__(self) -> "QSqrt5":
        return QSqrt5(-self.a, -self.b)

    def __pow__(self, n: int) -> "QSqrt5":
        if n < 0:
            return (~self) ** (-n)
        result = QSqrt5(Fraction(1), Fraction(0))
        base = self
        curr_n = n
        while curr_n > 0:
            if curr_n % 2 == 1:
                result = result * base
            base = base * base
            curr_n //= 2
        return result

    def __invert__(self) -> "QSqrt5":
        # 1 / (a + b*sqrt(5)) = (a - b*sqrt(5)) / (a^2 - 5*b^2)
        denom = self.a * self.a - Fraction(5) * self.b * self.b
        if denom == 0:
            raise ZeroDivisionError(f"Element {self} is zero or degenerate in Q(sqrt(5)).")
        return QSqrt5(self.a / denom, -self.b / denom)

    def is_rational(self) -> bool:
        return self.b == 0


def fold(x: int) -> QSqrt5:
    """Folds an integer into an exact Q(sqrt(5)) field element."""
    return QSqrt5(Fraction(x), Fraction(0))


def unfold(y: QSqrt5) -> int:
    """
    Unfolds a Q(sqrt(5)) element back to an exact integer.
    Raises ValueError if the element has non-zero irrational b component.
    """
    if y.b != 0:
        raise ValueError(f"Cannot unfold element {y} with non-zero irrational component {y.b}*sqrt(5).")
    if y.a.denominator != 1:
        raise ValueError(f"Cannot unfold non-integer fraction {y.a} to int.")
    return y.a.numerator


# Golden Ratio phi = (1 + sqrt(5)) / 2 and conjugate psi = (1 - sqrt(5)) / 2
PHI = QSqrt5(Fraction(1, 2), Fraction(1, 2))
PSI = QSqrt5(Fraction(1, 2), Fraction(-1, 2))


def lucas_binet(n: int) -> QSqrt5:
    """
    Computes the n-th Lucas number L_n via exact Binet symbolic expansion:
    L_n = phi^n + psi^n
    """
    if n < 0:
        raise ValueError(f"Lucas index n must be non-negative, got {n}")
    return (PHI ** n) + (PSI ** n)


def lucas_recurrence(n: int) -> int:
    """Computes n-th Lucas number via standard integer recurrence L_0=2, L_1=1, L_n=L_{n-1}+L_{n-2}."""
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
