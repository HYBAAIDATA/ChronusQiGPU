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


def _nonnegative_index(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("Lucas/Fibonacci index must be a non-negative integer")
    return n


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

    @classmethod
    def from_rational(
        cls,
        a_num: int,
        a_den: int,
        b_num: int,
        b_den: int,
    ) -> "QSqrt5":
        """Construct from separate rational coefficients, as the legacy API allowed."""
        return cls(Fraction(a_num, a_den), Fraction(b_num, b_den))

    def conjugate(self) -> "QSqrt5":
        return QSqrt5(self.a, -self.b)

    def norm(self) -> Fraction:
        """Exact field norm N(a + b*sqrt(5)) = a^2 - 5*b^2."""
        return self.a * self.a - Fraction(5) * self.b * self.b

    def to_dict(self) -> dict:
        return {
            "a_num": self.a.numerator,
            "a_den": self.a.denominator,
            "b_num": self.b.numerator,
            "b_den": self.b.denominator,
            "exact_representation": f"({self.a}) + ({self.b})*sqrt(5)",
        }

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
        if not isinstance(n, int) or isinstance(n, bool):
            raise ValueError("field exponent must be an integer")
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
        denom = self.norm()
        if denom == 0:
            raise ZeroDivisionError(f"Element {self} is zero or degenerate in Q(sqrt(5)).")
        conjugate = self.conjugate()
        return QSqrt5(conjugate.a / denom, conjugate.b / denom)

    def __truediv__(self, other: "QSqrt5") -> "QSqrt5":
        if not isinstance(other, QSqrt5):
            return NotImplemented
        return self * ~other

    def is_rational(self) -> bool:
        return self.b == 0


def fold(x: int) -> QSqrt5:
    """Fold an integer into an exact Q(sqrt(5)) field element."""
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError("fold input must be an integer")
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


SQRT5 = QSqrt5(Fraction(0), Fraction(1))


def lucas_binet(n: int) -> QSqrt5:
    """Compute L_n = phi^n + psi^n by exact symbolic Binet expansion."""
    _nonnegative_index(n)
    return (PHI ** n) + (PSI ** n)


def fibonacci_binet(n: int) -> QSqrt5:
    """Compute F_n = (phi^n - psi^n) / sqrt(5) exactly."""
    _nonnegative_index(n)
    return ((PHI ** n) - (PSI ** n)) / SQRT5


def lucas_recurrence(n: int) -> int:
    """Compute L_n by the independent linear integer recurrence."""
    _nonnegative_index(n)
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fibonacci_fast(n: int) -> int:
    """Compute F_n through the canonical exact Z[phi] fast-doubling engine."""
    _nonnegative_index(n)
    from chronus.backends.lattice import phi_power

    return phi_power(n).b


def lucas_fast(n: int) -> int:
    """Compute L_n through the canonical metallic fast-doubling engine."""
    _nonnegative_index(n)
    from chronus.backends.metallic import metallic_sequence

    return metallic_sequence(1, n)
