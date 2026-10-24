"""
GQF Family 10 — Mathematical Identities Unit Tests

Tests d'Ocagne's identity, Honsberger's identity, Fibonacci polynomials,
and Lucas polynomials.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from golden_quantum.math_identities import (
    docagne_identity, docagne_distance, fib_signed,
    honsberger_identity, honsberger_compose,
    fib_poly_coeffs, lucas_poly_coeffs,
    fib_poly_eval, lucas_poly_eval,
    fib_poly_specialization, lucas_poly_specialization,
    lucas_fib_relation,
)
from golden_quantum.sequences import fibonacci, lucas


# ═══════════════════════════════════════════════════════════════════
# d'OCAGNE'S IDENTITY
# ═══════════════════════════════════════════════════════════════════

class TestDocagne:

    def test_basic_m_gt_n(self):
        assert docagne_identity(5, 3)

    def test_basic_m_eq_n(self):
        assert docagne_identity(7, 7)

    def test_basic_m_lt_n(self):
        assert docagne_identity(3, 5)

    def test_grid_m_gt_n(self):
        for m in range(1, 100):
            for n in range(1, m):
                assert docagne_identity(m, n), f"Failed at m={m}, n={n}"

    def test_grid_m_lt_n(self):
        for m in range(1, 50):
            for n in range(m + 1, m + 30):
                assert docagne_identity(m, n), f"Failed at m={m}, n={n}"

    def test_m_eq_n_is_zero(self):
        """When m=n, both sides of d'Ocagne equal 0."""
        for n in range(0, 200):
            assert docagne_identity(n, n)

    def test_distance_matches_direct(self):
        for m in range(0, 100):
            for n in range(0, 100):
                assert docagne_distance(m, n) == fib_signed(m - n)

    def test_large_indices(self):
        assert docagne_identity(1000, 500)
        assert docagne_identity(5000, 2500)
        assert docagne_identity(10000, 9999)


# ═══════════════════════════════════════════════════════════════════
# SIGNED FIBONACCI
# ═══════════════════════════════════════════════════════════════════

class TestSignedFibonacci:

    def test_zero(self):
        assert fib_signed(0) == 0

    def test_positive(self):
        assert fib_signed(10) == 55

    def test_negative_odd(self):
        """F_{-k} = (-1)^{k+1} * F_k. For k=1: F_{-1} = 1."""
        assert fib_signed(-1) == 1

    def test_negative_even(self):
        """For k=2: F_{-2} = -1."""
        assert fib_signed(-2) == -1

    def test_negative_grid(self):
        for k in range(1, 100):
            expected = (1 if k % 2 == 1 else -1) * fibonacci(k)
            assert fib_signed(-k) == expected


# ═══════════════════════════════════════════════════════════════════
# HONSBERGER'S IDENTITY
# ═══════════════════════════════════════════════════════════════════

class TestHonsberger:

    def test_basic(self):
        assert honsberger_identity(4, 3)

    def test_k_zero(self):
        """F_{n-1}*F_0 + F_n*F_1 = F_n. So F_{n+0} = F_n."""
        assert honsberger_identity(5, 0)

    def test_n_one(self):
        """F_0*F_k + F_1*F_{k+1} = F_{k+1}."""
        assert honsberger_identity(1, 10)

    def test_grid(self):
        for n in range(1, 80):
            for k in range(0, 80):
                assert honsberger_identity(n, k), f"Failed at n={n}, k={k}"

    def test_compose_correct(self):
        for n in range(1, 50):
            for k in range(0, 50):
                result = honsberger_compose(n, k)
                assert result[0] == n + k
                assert result[1] == fibonacci(n + k)
                assert result[2] == fibonacci(n + k + 1)

    def test_large_indices(self):
        assert honsberger_identity(1000, 500)
        assert honsberger_identity(5000, 2500)


# ═══════════════════════════════════════════════════════════════════
# FIBONACCI POLYNOMIALS
# ═══════════════════════════════════════════════════════════════════

class TestFibonacciPolynomial:

    def test_base_cases(self):
        assert fib_poly_coeffs(0) == [0]
        assert fib_poly_coeffs(1) == [1]

    def test_known_coeffs(self):
        assert fib_poly_coeffs(2) == [0, 1]       # x
        assert fib_poly_coeffs(3) == [1, 0, 1]   # x² + 1
        assert fib_poly_coeffs(4) == [0, 2, 0, 1] # x³ + 2x
        assert fib_poly_coeffs(5) == [1, 0, 3, 0, 1]  # x⁴ + 3x² + 1

    def test_recurrence(self):
        for n in range(2, 50):
            for x in [0, 1, 2, 3, -1, -2, 10]:
                fn = fib_poly_eval(n, x)
                fnm1 = fib_poly_eval(n - 1, x)
                fnm2 = fib_poly_eval(n - 2, x)
                assert fn == x * fnm1 + fnm2, f"Recurrence fails at n={n}, x={x}"

    def test_specialization_at_1(self):
        for n in range(0, 200):
            assert fib_poly_specialization(n), f"F_{n}(1) != F_{n}"

    def test_eval_at_0(self):
        """F_n(0) = F_{n-2}(0) + 0 = ... = 1 if n odd, 0 if n even."""
        for n in range(0, 50):
            val = fib_poly_eval(n, 0)
            # F_n(0) = 0 for even n, 1 for odd n
            assert val == (n % 2 if n > 0 else 0)

    def test_degree(self):
        """F_n(x) has degree n-1 for n >= 1."""
        for n in range(1, 30):
            coeffs = fib_poly_coeffs(n)
            assert coeffs[-1] != 0  # Leading coefficient nonzero
            assert len(coeffs) == n  # Degree n-1 means n coefficients


# ═══════════════════════════════════════════════════════════════════
# LUCAS POLYNOMIALS
# ═══════════════════════════════════════════════════════════════════

class TestLucasPolynomial:

    def test_base_cases(self):
        assert lucas_poly_coeffs(0) == [2]
        assert lucas_poly_coeffs(1) == [0, 1]

    def test_known_coeffs(self):
        assert lucas_poly_coeffs(2) == [2, 0, 1]       # x² + 2
        assert lucas_poly_coeffs(3) == [0, 3, 0, 1]   # x³ + 3x
        assert lucas_poly_coeffs(4) == [2, 0, 4, 0, 1] # x⁴ + 4x² + 2

    def test_recurrence(self):
        for n in range(2, 50):
            for x in [0, 1, 2, 3, -1, -2, 10]:
                ln = lucas_poly_eval(n, x)
                lnm1 = lucas_poly_eval(n - 1, x)
                lnm2 = lucas_poly_eval(n - 2, x)
                assert ln == x * lnm1 + lnm2, f"Recurrence fails at n={n}, x={x}"

    def test_specialization_at_1(self):
        for n in range(0, 200):
            assert lucas_poly_specialization(n), f"L_{n}(1) != L_{n}"

    def test_degree(self):
        """L_n(x) has degree n for n >= 1."""
        for n in range(1, 30):
            coeffs = lucas_poly_coeffs(n)
            assert coeffs[-1] != 0
            assert len(coeffs) == n + 1  # Degree n means n+1 coefficients


# ═══════════════════════════════════════════════════════════════════
# LUCAS-FIBONACCI POLYNOMIAL RELATION
# ═══════════════════════════════════════════════════════════════════

class TestLucasFibRelation:

    def test_relation_holds(self):
        """L_n(x) = F_{n-1}(x) + F_{n+1}(x) for n >= 1."""
        for n in range(1, 100):
            assert lucas_fib_relation(n), f"Relation fails at n={n}"

    def test_relation_eval(self):
        """Verify relation at specific evaluation points."""
        for n in range(1, 30):
            for x in [0, 1, 2, 3, -1, 5]:
                ln = lucas_poly_eval(n, x)
                fnm1 = fib_poly_eval(n - 1, x)
                fnp1 = fib_poly_eval(n + 1, x)
                assert ln == fnm1 + fnp1, f"Fails at n={n}, x={x}"

    def test_relation_at_1(self):
        """At x=1: L_n = F_{n-1} + F_{n+1} (standard identity)."""
        for n in range(1, 100):
            assert lucas(n) == fibonacci(n - 1) + fibonacci(n + 1)
