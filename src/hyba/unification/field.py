"""Experimental exact arithmetic; not integrated or release-qualified.

For zeta = exp(2*pi*i/5), phi = -(zeta**2 + zeta**3). This gives an
embedding Q(phi) -> Q(zeta_5), NOT an isomorphism Q(phi) -> Z[zeta_5].
Q(phi) maps to the real subfield of Q(zeta_5); its integer-coefficient
subset Z[phi] maps to the real subring Z[zeta_5] intersected with it.
The 4-tuple returned here is a coordinate vector, not a new ring engine.
"""
from dataclasses import dataclass
from fractions import Fraction


def _exact(value):
    if type(value) is int or type(value) is Fraction:
        return Fraction(value)
    raise TypeError('coefficients must be int or Fraction (not bool or float)')


@dataclass(frozen=True)
class QPhi:
    """The exact number a + b*phi with phi**2 = phi + 1."""
    a: Fraction
    b: Fraction

    def __post_init__(self):
        object.__setattr__(self, 'a', _exact(self.a))
        object.__setattr__(self, 'b', _exact(self.b))

    def __add__(self, other):
        if not isinstance(other, QPhi):
            return NotImplemented
        return QPhi(self.a + other.a, self.b + other.b)

    def __neg__(self):
        return QPhi(-self.a, -self.b)

    def __sub__(self, other):
        if not isinstance(other, QPhi):
            return NotImplemented
        return self + (-other)

    def __mul__(self, other):
        if not isinstance(other, QPhi):
            return NotImplemented
        return QPhi(self.a * other.a + self.b * other.b,
                    self.a * other.b + self.b * other.a + self.b * other.b)

    def inverse(self):
        norm = self.a * self.a + self.a * self.b - self.b * self.b
        if norm == 0:
            raise ZeroDivisionError('zero has no multiplicative inverse')
        return QPhi((self.a + self.b) / norm, -self.b / norm)

    def __truediv__(self, other):
        if not isinstance(other, QPhi):
            return NotImplemented
        return self * other.inverse()

    def __pow__(self, n):
        if type(n) is not int:
            raise TypeError('exponent must be an integer')
        base = self if n >= 0 else self.inverse()
        n = abs(n)
        result = QPhi(1, 0)
        while n:
            if n & 1:
                result = result * base
            base = base * base
            n //= 2
        return result

    def cyclotomic_coordinates(self):
        """Rational power-basis coordinates in Q(zeta_5)."""
        return (self.a, Fraction(0), -self.b, -self.b)

    def integral_cyclotomic_coordinates(self):
        """Coordinates in Z[zeta_5], rejecting elements with denominators."""
        c = self.cyclotomic_coordinates()
        if any(x.denominator != 1 for x in c):
            raise ValueError('not in Z[zeta_5]')
        return tuple(x.numerator for x in c)

    @classmethod
    def from_cyclotomic_coordinates(cls, coordinates):
        """Invert the embedding only on the real subfield; reject other inputs."""
        if not isinstance(coordinates, (tuple, list)) or len(coordinates) != 4:
            raise ValueError('expected four power-basis coefficients')
        c = tuple(_exact(x) for x in coordinates)
        if c[1] != 0 or c[2] != c[3]:
            raise ValueError('not in the real subfield Q(phi)')
        return cls(c[0], -c[2])

@dataclass(frozen=True)
class Zeta5:
    """Strict integer-coefficient adapter around a trusted CyclotomicZ5 backend.

    Backend must be the repository's CyclotomicZ5 class. It is injected to avoid
    importing the security package and its unrelated side effects. The adapter
    validates input and output coefficients; it does not verify backend math.
    """
    coefficients: tuple
    backend: type

    def __post_init__(self):
        if not isinstance(self.coefficients, tuple) or len(self.coefficients) != 4:
            raise ValueError('expected a tuple of four integers')
        if any(type(x) is not int for x in self.coefficients):
            raise TypeError('ring coefficients must be integers, not bool or float')
        if not isinstance(self.backend, type):
            raise TypeError('backend must be the trusted ring class')

    def _element(self):
        return self.backend(*self.coefficients)

    def _binary(self, other, operation):
        if not isinstance(other, Zeta5) or self.backend is not other.backend:
            raise TypeError('operands must use the same trusted ring backend')
        result = operation(self._element(), other._element())
        return Zeta5((result.c0, result.c1, result.c2, result.c3), self.backend)

    def __add__(self, other):
        return self._binary(other, lambda x,y: x+y)

    def __sub__(self, other):
        return self._binary(other, lambda x,y: x-y)

    def __mul__(self, other):
        return self._binary(other, lambda x,y: x*y)

    def __neg__(self):
        return Zeta5(tuple(-x for x in self.coefficients), self.backend)

    def __pow__(self, exponent):
        if type(exponent) is not int or exponent < 0:
            raise ValueError('ring exponent must be a nonnegative integer')
        result = Zeta5((1,0,0,0), self.backend)
        base = self
        while exponent:
            if exponent & 1:
                result = result * base
            base = base * base
            exponent //= 2
        return result

    def to_qphi(self):
        return QPhi.from_cyclotomic_coordinates(self.coefficients)

    @classmethod
    def from_qphi(cls, value, backend):
        if not isinstance(value, QPhi):
            raise TypeError('expected QPhi')
        return cls(value.integral_cyclotomic_coordinates(), backend)
