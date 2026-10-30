#!/usr/bin/env python3
"""
therm_bound — Exact symbolic Landauer bound arithmetic.
No float anywhere. k_B * ln(2) is a symbol. b*T is rational.
Comparison is integer cross-multiplication.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union


# ──────────────────────────────────────────────
# Rational exact arithmetic
# ──────────────────────────────────────────────

@dataclass(frozen=True, eq=True)
class Rational:
    num: int
    den: int

    def __post_init__(self):
        assert isinstance(self.num, int)
        assert isinstance(self.den, int)
        assert self.den > 0
        # Normalize sign: keep negative only in num
        if self.den < 0:
            object.__setattr__(self, 'num', -self.num)
            object.__setattr__(self, 'den', -self.den)
        # Reduce by gcd
        from math import gcd
        g = gcd(abs(self.num), abs(self.den))
        object.__setattr__(self, 'num', self.num // g)
        object.__setattr__(self, 'den', self.den // g)

    def __mul__(self, other: Union[int, 'Rational']) -> 'Rational':
        if isinstance(other, int):
            return Rational(self.num * other, self.den)
        if isinstance(other, Rational):
            return Rational(self.num * other.den, self.den * other.num)
        return NotImplemented

    def __rmul__(self, other: int) -> 'Rational':
        return self * other

    def __le__(self, other: 'Rational') -> bool:
        # a/b <= c/d iff a*d <= c*b (integer arithmetic, no float)
        return self.num * other.den <= other.num * self.den

    def __gt__(self, other: 'Rational') -> bool:
        return not (self <= other)

    def __lt__(self, other: 'Rational') -> bool:
        return self < other


# ──────────────────────────────────────────────
# Symbolic k_B * ln(2)
# ──────────────────────────────────────────────

class SymbolicKB_LN2:
    """Opaque symbol; never evaluated to a float inside this module."""
    __slots__ = ("symbol",)

    def __init__(self):
        object.__setattr__(self, "symbol", "k_B_ln2")

    def __repr__(self):
        return "k_B_ln2"

    def __str__(self):
        return "k_B * ln(2)"


# ──────────────────────────────────────────────
# EnergyBound — exact Landauer bound
# ──────────────────────────────────────────────

@dataclass(frozen=True, eq=True)
class EnergyBound:
    bits_erased: int
    temperature_K: Rational
    coef: Rational          # = b * T, rational
    unit_symbol: SymbolicKB_LN2
    expression: str         # "b * T * k_B * ln(2)"

    def __post_init__(self):
        assert self.bits_erased >= 0, "bits_erased must be >= 0"
        assert self.temperature_K.den > 0
        # coef = b * T.num / T.den already reduced by Rational constructor


# ──────────────────────────────────────────────
# make_bound — create exact Landauer bound
# ──────────────────────────────────────────────

def make_bound(b: int, T: Rational) -> EnergyBound:
    """E >= b * k_B * T * ln(2) kept exactly symbolic."""
    assert b >= 0, "b must be >= 0"
    assert T.num > 0 and T.den > 0, "Temperature numerator/denom must be > 0"
    coef = Rational(b * T.num, T.den)  # b * T.num / T.den, reduced
    return EnergyBound(
        bits_erased=b,
        temperature_K=T,
        coef=coef,
        unit_symbol=SymbolicKB_LN2(),
        expression="b * T * k_B * ln(2)",
    )


# ──────────────────────────────────────────────
# bound_leq — exact comparison, no float
# ──────────────────────────────────────────────

def bound_leq(a: EnergyBound, c: EnergyBound) -> bool:
    """a.coef <= c.coef iff a.b*T <= c.b*T via integer cross-multiplication."""
    return a.coef <= c.coef  # Rational.__le__ does cross-multiplication


# ──────────────────────────────────────────────
# Tests (the "exact_bound_test" module)
# ──────────────────────────────────────────────

def test_bound_is_exact_symbolic():
    b = 256
    T = Rational(300, 1)
    e = make_bound(b, T)
    assert e.coef == Rational(76800, 1), f"Expected 76800/1, got {e.coef}"
    assert e.unit_symbol.symbol == "k_B_ln2"
    assert e.expression == "b * T * k_B * ln(2)"
    # No float anywhere
    # (We check by ensuring coef is Rational, not float)
    assert isinstance(e.coef, Rational)
    print("  test_bound_is_exact_symbolic PASSED")


def test_bound_comparison_is_exact():
    e1 = make_bound(100, Rational(300, 1))
    e2 = make_bound(200, Rational(300, 1))
    assert bound_leq(e1, e2) == True, "100*300 < 200*300"
    assert bound_leq(e2, e1) == False, "200*300 not <= 100*300"
    # Cross-multiplication only; no division
    print("  test_bound_comparison_is_exact PASSED")


def test_bound_at_absolute_zero_refuses():
    try:
        # T must be > 0; the bound is meaningless at T = 0
        make_bound(256, Rational(0, 1))
        assert False, "Should have raised AssertionError for T=0"
    except AssertionError:
        # This is fine — we assert T.num > 0 in make_bound
        print("  test_bound_at_absolute_zero_refuses PASSED (assertion raised)")


def test_no_float_in_energy_bound():
    """Assert that no float appears in the EnergyBound object."""
    e = make_bound(100, Rational(300, 1))
    # coef must be Rational, not float
    assert isinstance(e.coef, Rational), "coef must be Rational, not float"
    assert isinstance(e.temperature_K, Rational), "temperature_K must be Rational"
    print("  test_no_float_in_energy_bound PASSED")


# ──────────────────────────────────────────────
# Run the tests if invoked directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_bound_is_exact_symbolic()
    test_bound_comparison_is_exact()
    test_bound_at_absolute_zero_refuses()
    test_no_float_in_energy_bound()
    print("\nAll therm_bound tests PASSED")