import sys
import unittest
from fractions import Fraction
from chronus.math.binet_lucas import QSqrt5, fold, unfold, lucas_binet, lucas_recurrence


class TestBinetLucas(unittest.TestCase):
    def test_qsqrt5_arithmetic(self):
        q1 = QSqrt5(Fraction(1), Fraction(2))
        q2 = QSqrt5(Fraction(3), Fraction(4))

        # Add
        q_sum = q1 + q2
        self.assertEqual(q_sum, QSqrt5(Fraction(4), Fraction(6)))

        # Sub
        q_diff = q2 - q1
        self.assertEqual(q_diff, QSqrt5(Fraction(2), Fraction(2)))

        # Neg
        q_neg = -q1
        self.assertEqual(q_neg, QSqrt5(Fraction(-1), Fraction(-2)))

        # Mul
        # (1 + 2sqrt5)*(3 + 4sqrt5) = 3 + 4sqrt5 + 6sqrt5 + 40 = 43 + 10sqrt5
        q_prod = q1 * q2
        self.assertEqual(q_prod, QSqrt5(Fraction(43), Fraction(10)))

        # Inverse
        inv_q1 = ~q1
        # 1 / (1 + 2*sqrt(5)) = (1 - 2*sqrt(5)) / (1 - 20) = -1/19 + 2/19*sqrt(5)
        self.assertEqual(inv_q1.a, Fraction(-1, 19))
        self.assertEqual(inv_q1.b, Fraction(2, 19))
        self.assertEqual(q1 * inv_q1, QSqrt5(Fraction(1), Fraction(0)))

    def test_qsqrt5_zero_division(self):
        q_zero = QSqrt5(Fraction(0), Fraction(0))
        with self.assertRaises(ZeroDivisionError):
            _ = ~q_zero

    def test_fold_unfold_round_trip(self):
        for x in [0, 1, -1, 42, -999, 1000000]:
            f = fold(x)
            self.assertEqual(unfold(f), x)

    def test_unfold_invalid_cases(self):
        # Irrational component b != 0
        q_irrational = QSqrt5(Fraction(5), Fraction(1))
        with self.assertRaises(ValueError):
            unfold(q_irrational)

        # Fractional rational component denominator != 1
        q_fraction = QSqrt5(Fraction(1, 2), Fraction(0))
        with self.assertRaises(ValueError):
            unfold(q_fraction)

    def test_lucas_n_100_binet_vs_recurrence(self):
        """B3.5: L_n = phi^n + psi^n verified symbolically for n <= 100."""
        for n in range(0, 101):
            binet_val = lucas_binet(n)
            rec_val = lucas_recurrence(n)
            self.assertTrue(binet_val.is_rational())
            self.assertEqual(unfold(binet_val), rec_val)

    def test_lucas_negative_index_raises(self):
        with self.assertRaises(ValueError):
            lucas_binet(-1)

    def test_constant_memory_structural_footprint(self):
        """B3.6: Verify <1 KB structural memory claim for exact field element."""
        q = lucas_binet(100)
        size_bytes = sys.getsizeof(q) + sys.getsizeof(q.a) + sys.getsizeof(q.b)
        self.assertLess(size_bytes, 1024, f"Element memory {size_bytes} bytes exceeds 1 KB!")


if __name__ == "__main__":
    unittest.main()
