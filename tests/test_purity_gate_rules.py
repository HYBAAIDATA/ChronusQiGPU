"""The purity gate bans floating-point math in exact paths but allows exact integer helpers."""
import importlib.util
import math
import pytest
from pathlib import Path

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("purity_gate", ROOT / "scripts" / "ci" / "purity_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
MATH_RULE = gate.BANNED[0][0]


def test_exact_integer_helpers_are_allowed():
    for line in ("r = math.isqrt(n)", "g = math.gcd(a, b)", "m = math.lcm(a, b)",
                 "c = math.comb(n, k)", "p = math.perm(n, k)", "f = math.factorial(n)"):
        assert MATH_RULE.search(line) is None, line


def test_floating_point_math_is_rejected():
    for line in ("y = math.sqrt(x)", "y = math.log(x)", "y = math.pi", "y = math.exp(x)",
                 "y = math.fsum(xs)", "y = math.gcd_float(x)", "y = math.isqrt2(x)"):
        assert MATH_RULE.search(line) is not None, line


def test_allowed_helpers_are_integer_only():
    assert math.gcd(0x9E3779B9, 1 << 32) == 1
    for helper, args in ((math.gcd, (2.0, 4)), (math.isqrt, (9.0,)), (math.comb, (4.0, 2))):
        try:
            helper(*args)
        except TypeError:
            continue
        raise AssertionError(f"{helper.__name__} accepted a float")
