"""Golden core: canonical Layer 0 of the HYBA golden substrate (exact arithmetic).

Owner-declared canonical (2026-11-17). Substrate vocabulary (owner declaration
D5): Lucas and Pisot scale; Zeckendorf and Binet fold; Fibonacci and Cassini
store.

Provenance: Layer 0 of ``hyba_golden_dropin.py`` v4.5.0 (owner-supplied,
SHA-256 2c260935394ffaac345b323a87c398fcd75fdc72f262627c0b9d721b36629166).
Only Layer 0 is canonical. Layers 1-4 of that file are not part of this module.

Canonical owners are preserved (D9), so this module adds no second engine:

* Fibonacci and Lucas for n >= 0 delegate to the existing canonical exact
  engines (``chronus.math.binet_lucas.fibonacci_fast`` -> Z[phi] lattice,
  ``lucas_fast`` -> metallic). This module adds negative indices through the
  exact identities F(-n) = (-1)^(n+1) F(n) and L(-n) = (-1)^n L(n).
* The M15 byte-pair fold is the same transform as
  ``chronus.tensor.folded_state`` (M15 = [[219, 98], [98, 121]] mod 256, inverse
  [[135, 98], [98, 37]], det = -1 mod 256, odd input padded with a zero byte).
  It is provided here in pure Python for small payloads; the tests check it is
  byte-identical to the folded_state tables over all 65,536 byte pairs.

Exactness: every integer function is exact. The Pisot family's dominant roots
are irrational; the exact object is the minimal polynomial (``FAMILY_COEFFS``).
``family_root`` returns a decimal value together with a certified enclosure
(an exact rational interval on which the polynomial changes sign), so the
error bound is proven rather than assumed. Decimal precision is set in a local
context and never changes the process-wide decimal context.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from math import isqrt
from typing import Dict, List, Tuple

from chronus.math.binet_lucas import fibonacci_fast, lucas_fast

__all__ = [
    "FAMILY_COEFFS", "FOLD_MODULUS", "M15", "M15_INV", "RootEnclosure",
    "cassini_check", "family_pisot_modulus", "family_pisot_modulus_enclosure", "family_root", "fibonacci", "lucas",
    "t_phi_fold", "t_phi_unfold", "zeckendorf_decode", "zeckendorf_encode",
]


def _index(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("index must be an int")
    return n


# --------------------------------------------------------- store: Fibonacci, Cassini
def fibonacci(n: int) -> int:
    """Exact F(n) for any integer n (negafibonacci for n < 0)."""
    n = _index(n)
    if n >= 0:
        return fibonacci_fast(n)
    m = -n
    return (-1) ** (m + 1) * fibonacci_fast(m)


def lucas(n: int) -> int:
    """Exact L(n) for any integer n; L(-n) = (-1)^n L(n)."""
    n = _index(n)
    if n >= 0:
        return lucas_fast(n)
    m = -n
    return (-1) ** m * lucas_fast(m)


def cassini_check(n: int) -> bool:
    """Cassini identity witness: F(n+1) F(n-1) - F(n)^2 == (-1)^n (exact, any integer n)."""
    n = _index(n)
    return fibonacci(n + 1) * fibonacci(n - 1) - fibonacci(n) ** 2 == (-1) ** n


# ------------------------------------------------------------ fold: Zeckendorf
def zeckendorf_encode(n: int) -> List[int]:
    """Indices k >= 2 (descending, no two consecutive) with sum F(k) == n; [] for n == 0."""
    n = _index(n)
    if n < 0:
        raise ValueError("Zeckendorf representation is defined for n >= 0")
    if n == 0:
        return []
    fibs = [(2, 1), (3, 2)]
    while fibs[-1][1] <= n:
        k = fibs[-1][0] + 1
        fibs.append((k, fibs[-1][1] + fibs[-2][1]))
    out, rest = [], n
    for k, value in reversed(fibs):
        if value <= rest:
            out.append(k)
            rest -= value
            if rest == 0:
                break
    return out


def zeckendorf_decode(indices: List[int]) -> int:
    """Sum of F(k); rejects indices that are not a valid Zeckendorf representation."""
    ks = list(indices)
    if any(not isinstance(k, int) or isinstance(k, bool) or k < 2 for k in ks):
        raise ValueError("Zeckendorf indices must be integers >= 2")
    ordered = sorted(ks, reverse=True)
    if len(set(ordered)) != len(ordered) or any(a - b < 2 for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Zeckendorf indices must be distinct and non-consecutive")
    return sum(fibonacci(k) for k in ordered)


# ---------------------------------------------------------------- scale: Pisot
FAMILY_COEFFS: Dict[str, Tuple[int, ...]] = {
    "golden": (1, -1, -1),           # x^2 - x - 1
    "silver": (1, -2, -1),           # x^2 - 2x - 1
    "plastic": (1, 0, -1, -1),       # x^3 - x - 1
    "supergolden": (1, -1, 0, -1),   # x^3 - x^2 - 1
    "tribonacci": (1, -1, -1, -1),   # x^3 - x^2 - x - 1
}


def _polyval(coeffs, x):
    acc = 0 * x
    for c in coeffs:
        acc = acc * x + c
    return acc


@dataclass(frozen=True)
class RootEnclosure:
    """Dominant real root: decimal value plus an exact rational bracket [low, high] containing it."""
    family: str
    value: Decimal
    low: Fraction
    high: Fraction

    @property
    def width(self) -> Fraction:
        return self.high - self.low


def family_root(name: str, precision: int = 50) -> RootEnclosure:
    """Dominant real root (> 1) of the family's minimal polynomial, certified to ``precision`` digits."""
    if name not in FAMILY_COEFFS:
        raise KeyError(f"unknown Pisot family {name!r}; known: {', '.join(FAMILY_COEFFS)}")
    if not isinstance(precision, int) or precision < 5:
        raise ValueError("precision must be an int >= 5")
    coeffs = FAMILY_COEFFS[name]
    deg = len(coeffs) - 1
    deriv = [c * (deg - i) for i, c in enumerate(coeffs[:-1])]
    with localcontext() as ctx:
        ctx.prec = precision + 10
        x = Decimal(3) / Decimal(2)
        tol = Decimal(10) ** (-(precision + 2))
        for _ in range(8 * precision):
            step = _polyval([Decimal(c) for c in coeffs], x) / _polyval([Decimal(c) for c in deriv], x)
            x -= step
            if abs(step) < tol:
                break
        value = +x
    half = Fraction(1, 10 ** precision)
    centre = Fraction(value)
    low, high = centre - half, centre + half
    f_low, f_high = _polyval(coeffs, low), _polyval(coeffs, high)
    if f_low == 0 or f_high == 0 or (f_low > 0) == (f_high > 0):
        raise ArithmeticError(f"{name}: Newton result could not be certified by a sign change")
    if low <= 1:
        raise ArithmeticError(f"{name}: dominant root is not > 1")
    with localcontext() as ctx:
        ctx.prec = precision + 2
        return RootEnclosure(name, +value, low, high)


def _sqrt_bounds(q: Fraction, bits: int) -> Tuple[Fraction, Fraction]:
    """Exact rational bounds lo <= sqrt(q) <= hi with hi - lo <= 2**-bits (q >= 0)."""
    n = q * (1 << (2 * bits))  # sqrt(n) = sqrt(q) * 2**bits
    floor_n = n.numerator // n.denominator
    ceil_n = -((-n.numerator) // n.denominator)
    lo = isqrt(floor_n)
    hi = isqrt(ceil_n)
    if hi * hi < ceil_n:
        hi += 1
    return Fraction(lo, 1 << bits), Fraction(hi, 1 << bits)


def family_pisot_modulus_enclosure(name: str, precision: int = 50) -> Tuple[Fraction, Fraction]:
    """Exact rational bracket (low, high) certified to contain the largest conjugate modulus.

    Quadratic families: the conjugate is -c0 / alpha (product of the roots), so |mu| = |c0| / alpha.
    Cubic families here have one real root and a complex-conjugate pair, so |mu|^2 = |c0| / alpha.
    The tests check that assumption (the deflated quadratic has a negative discriminant).
    alpha is bracketed by family_root's certified enclosure, so the bounds follow from it.
    """
    coeffs = FAMILY_COEFFS[name]
    root = family_root(name, precision)
    c0 = Fraction(abs(coeffs[-1]))
    ratio_low, ratio_high = c0 / root.high, c0 / root.low  # alpha in [low, high]
    if len(coeffs) - 1 == 2:
        return ratio_low, ratio_high
    low, _ = _sqrt_bounds(ratio_low, precision + 10)
    _, high = _sqrt_bounds(ratio_high, precision + 10)
    return low, high


def family_pisot_modulus(name: str, precision: int = 50) -> Decimal:
    """Display value for the largest conjugate modulus (< 1 for a Pisot number).

    Not exact: this is the midpoint of family_pisot_modulus_enclosure, rounded to
    ``precision`` digits. Use the enclosure for certified comparisons.
    """
    low, high = family_pisot_modulus_enclosure(name, precision)
    mid = (low + high) / 2
    with localcontext() as ctx:
        ctx.prec = precision
        return +(Decimal(mid.numerator) / Decimal(mid.denominator))


# ----------------------------------------------------------- fold: M15 over Z/256
M15: Tuple[Tuple[int, int], Tuple[int, int]] = ((219, 98), (98, 121))
M15_INV: Tuple[Tuple[int, int], Tuple[int, int]] = ((135, 98), (98, 37))
FOLD_MODULUS: int = 256


def t_phi_fold(raw: bytes) -> bytes:
    """M15 byte-pair fold mod 256 (same transform as chronus.tensor.folded_state); odd input gets a zero pad byte."""
    data = bytes(raw)
    if len(data) & 1:
        data += b"\x00"
    out = bytearray(len(data))
    (a, b), (c, d) = M15
    for i in range(0, len(data), 2):
        x, y = data[i], data[i + 1]
        out[i] = (a * x + b * y) % FOLD_MODULUS
        out[i + 1] = (c * x + d * y) % FOLD_MODULUS
    return bytes(out)


def t_phi_unfold(folded: bytes, original_len: int) -> bytes:
    """Exact inverse of ``t_phi_fold``; ``original_len`` removes the pad byte of odd input."""
    data = bytes(folded)
    if len(data) & 1:
        raise ValueError("folded data has odd length; it was not produced by t_phi_fold")
    if not isinstance(original_len, int) or not len(data) - 1 <= original_len <= len(data) or original_len < 0:
        raise ValueError("original_len does not match the folded length")
    out = bytearray(len(data))
    (a, b), (c, d) = M15_INV
    for i in range(0, len(data), 2):
        u, v = data[i], data[i + 1]
        out[i] = (a * u + b * v) % FOLD_MODULUS
        out[i + 1] = (c * u + d * v) % FOLD_MODULUS
    if original_len < len(out) and out[-1] != 0:
        raise ValueError("pad byte is not zero; folded data was altered or original_len is wrong")
    return bytes(out[:original_len])
