from chronus.mla1517.core import fib, lucas
from python_backend.core_modules.math_folding import (
    fibonacci_binet,
    fibonacci_cassini,
    lucas_binet,
    lucas_cassini,
    verify_cassini,
)


def test_exact_binet_matches_fast_doubling():
    for n in range(0, 256):
        assert fibonacci_binet(n) == fib(n)
        assert lucas_binet(n) == lucas(n)


def test_fibonacci_and_lucas_cassini_arbitrary_precision():
    for n in (1, 2, 3, 10, 100, 1_000, 10_000):
        assert fibonacci_cassini(n) == (-1) ** n
        assert lucas_cassini(n) == 5 * ((-1) ** (n - 1))
        assert verify_cassini(n)
