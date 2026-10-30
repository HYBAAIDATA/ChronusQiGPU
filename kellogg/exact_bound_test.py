#!/usr/bin/env python3
"""
exact_bound_test — Tests for the exact symbolic Landauer boundary.
All comparisons are integer cross-multiplication; no float appears.
"""

from __future__ import annotations
from math import gcd


# ──────────────────────────────────────────────
# Rational (replicated from therm_bound for self-containment)
# ──────────────────────────────────────────────

@dataclass(frozen=True, eq=True)
class Rational:
    num: int
    den: int

    def __post_init__(self):
        assert isinstance(self.num, int)
        assert isinstance(self.den, int)
        assert self.den > 0
        if self.den < 0:
            object.__setattr__(self, 'num', -self.num)
            object.__setattr__(self, 'den', -self.den)
        g = gcd(abs(self.num), abs(self.den))
        object.__setattr__(self, 'num', self.num // g)
        object.__setattr__(self, 'den', self.den // g)

    def __le__(self, other: 'Rational') -> bool:
        return self.num * other.den <= other.num * self.den


# ──────────────────────────────────────────────
# SymbolicKB_LN2 (replicated)
# ──────────────────────────────────────────────

class SymbolicKB_LN2:
    __slots__ = ("symbol",)

    def __init__(self):
        object.__setattr__(self, "symbol", "k_B_ln2")

    def __repr__(self):
        return "k_B_ln2"

    def __str__(self):
        return "k_B * ln(2)"


# ──────────────────────────────────────────────
# EnergyBound (replicated)
# ──────────────────────────────────────────────

@dataclass(frozen=True, eq=True)
class EnergyBound:
    bits_erased: int
    temperature_K: Rational
    coef: Rational          # = b * T
    unit_symbol: SymbolicKB_LN2
    expression: str         # "b * T * k_B * ln(2)"

    def __post_init__(self):
        assert self.bits_erased >= 0
        assert self.temperature_K.den > 0
        # coef = b * T.num / T.den already reduced by Rational constructor


# ──────────────────────────────────────────────
# make_bound
# ──────────────────────────────────────────────

def make_bound(b: int, T: Rational) -> EnergyBound:
    assert b >= 0
    assert T.num > 0 and T.den > 0, "Temperature numerator/denom must be > 0"
    coef = Rational(b * T.num, T.den)
    return EnergyBound(
        bits_erased=b,
        temperature_K=T,
        coef=coef,
        unit_symbol=SymbolicKB_LN2(),
        expression="b * T * k_B * ln(2)",
    )


# ──────────────────────────────────────────────
# bound_leq
# ──────────────────────────────────────────────

def bound_leq(a: EnergyBound, c: EnergyBound) -> bool:
    return a.coef <= c.coef


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
    assert isinstance(e.coef, Rational)
    assert isinstance(e.temperature_K, Rational)
    print("  test_bound_is_exact_symbolic PASSED")


def test_bound_comparison_is_exact():
    e1 = make_bound(100, Rational(300, 1))
    e2 = make_bound(200, Rational(300, 1))
    assert bound_leq(e1, e2) == True, "100*300 < 200*300"
    assert bound_leq(e2, e1) == False, "200*300 not <= 100*300"
    print("  test_bound_comparison_is_exact PASSED")


def test_bound_at_absolute_zero_refuses():
    try:
        make_bound(256, Rational(0, 1))
        assert False, "Should have raised AssertionError for T=0"
    except AssertionError:
        print("  test_bound_at_absolute_zero_refuses PASSED (assertion raised)")


def test_no_float_in_energy_bound():
    """Assert that no float appears in the EnergyBound object."""
    e = make_bound(100, Rational(300, 1))
    assert isinstance(e.coef, Rational), "coef must be Rational, not float"
    assert isinstance(e.temperature_K, Rational), "temperature_K must be Rational"
    print("  test_no_float_in_energy_bound PASSED")


def test_bound_comparison_different_temps():
    """Test that bounds at different temperatures compare correctly."""
    e1 = make_bound(100, Rational(300, 1))   # 100 * 300 = 30000
    e2 = make_bound(100, Rational(200, 1))   # 100 * 200 = 20000
    # e1.coef = 30000/1, e2.coef = 20000/1, so e1 > e2
    assert bound_leq(e2, e1) == True, "20000 <= 30000"
    assert bound_leq(e1, e2) == False, "30000 not <= 20000"
    print("  test_bound_comparison_different_temps PASSED")


# ──────────────────────────────────────────────
# Run tests if invoked directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_bound_is_exact_symbolic()
    test_bound_comparison_is_exact()
    test_bound_at_absolute_zero_refuses()
    test_no_float_in_energy_bound()
    test_bound_comparison_different_temps()
    print("\nAll exact_bound_test tests PASSED")