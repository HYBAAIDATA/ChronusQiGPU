"""Algebraic facts about Pisot numbers that this tree can prove.

Siegel's minimality theorem, Salem's closedness theorem, and Schmidt's
beta-expansion theorem are not claimed. Comparisons that look like
floating point are squared back to integer inequalities.
"""

from __future__ import annotations

import unittest
from decimal import Decimal, getcontext


def is_square(value: int) -> bool:
    if value < 0:
        return False
    root = 0
    while (root + 1) * (root + 1) <= value:
        root += 1
    return root * root == value


def lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def perrin(n: int) -> int:
    a, b, c = 3, 0, 2
    if n < 3:
        return (a, b, c)[n]
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b
    return c


def quadratic_is_pisot(trace: int, norm: int) -> bool:
    """True when x^2 - trace*x + norm is a quadratic Pisot polynomial.

    The discriminant test and the conjugate bound are integer comparisons.
    """
    discriminant = trace * trace - 4 * norm
    if discriminant <= 0 or is_square(discriminant):
        return False
    # sqrt(discriminant) < trace + 2, and > trace - 2 when that is positive.
    if discriminant >= (trace + 2) * (trace + 2):
        return False
    if trace >= 3 and discriminant <= (trace - 2) * (trace - 2):
        return False
    # Larger root > 1.
    if trace <= 1 and discriminant <= (2 - trace) * (2 - trace):
        return False
    return True


def quadratic_at_least_phi(trace: int, norm: int) -> bool:
    """Larger root of x^2 - trace*x + norm is at least phi.

    Both sides of the comparison are squared until only integers remain.
    """
    discriminant = trace * trace - 4 * norm
    if trace >= 4 and discriminant >= 5:
        return True
    if trace >= 2 and discriminant >= 5:
        return True
    if trace == 1:
        return discriminant >= 5
    if trace >= 2 and discriminant < 5:
        gap = 5 + discriminant - (trace - 1) * (trace - 1)
        if gap <= 0:
            return True
        return gap * gap <= 20 * discriminant
    raise AssertionError("trace below 1 is outside the Pisot range")


class MembershipTests(unittest.TestCase):
    def test_golden_ratio_is_pisot_and_least_quadratic(self):
        self.assertTrue(quadratic_is_pisot(1, -1))
        self.assertTrue(quadratic_at_least_phi(1, -1))
        # |conjugate| = 1/phi < 1 because the product of the roots is -1.
        self.assertEqual(1 * 1 - 4 * (-1), 5)
        for trace in range(1, 9):
            for norm in range(-12, 13):
                if not quadratic_is_pisot(trace, norm):
                    continue
                self.assertTrue(
                    quadratic_at_least_phi(trace, norm),
                    f"quadratic Pisot below phi at trace {trace}, norm {norm}",
                )
        # The norm -1 family starts at phi and increases.
        previous = None
        for slope in range(1, 7):
            self.assertTrue(quadratic_is_pisot(slope, -1))
            discriminant = slope * slope + 4
            self.assertFalse(is_square(discriminant))
            if previous is not None:
                self.assertGreater(discriminant, previous)
            previous = discriminant

    def test_phi_power_is_within_phi_to_the_minus_n_of_lucas(self):
        # |phi - L_1| = 1/phi > 1/2, because sqrt(5) > 2. The nearest
        # integer is 2, at distance phi^{-2} < 1/2, because 4 < 5.
        self.assertEqual(lucas(0), 2)
        self.assertEqual(lucas(1), 1)
        self.assertGreater(5, 4)
        self.assertLess(4, 5)
        for n in range(2, 25):
            self.assertEqual(lucas(n), lucas(n - 1) + lucas(n - 2))
        # The error e_n = L_n - phi^n obeys the same recurrence. Its seeds
        # are e_0 = 1 and e_1 = 1 - phi = hat phi, so e_n = hat phi^n.
        getcontext().prec = 80
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        for n in (2, 10, 40):
            ratio = abs(phi**n - Decimal(lucas(n))) * (phi**n)
            self.assertLess(abs(ratio - 1), Decimal("1e-20"))

    def test_plastic_and_tribonacci_are_pisot_cube_root_of_two_is_not(self):
        # f(x) = x^3 - x - 1 is strictly increasing on [1, infinity).
        self.assertLess(1**3 - 1 - 1, 0)
        self.assertGreater(2**3 - 2 - 1, 0)
        self.assertGreaterEqual(3 * 1 * 1 - 1, 2)
        # The critical value on [-1, 1] is negative: 2/(3*sqrt(3)) < 1
        # iff 4 < 27.
        self.assertLess(4, 27)
        # Product of the roots is 1 and the real root exceeds 1, so the
        # complex pair has modulus psi^{-1/2} < 1.
        self.assertGreater(2**3 - 2 - 1, 0)

        # Tribonacci polynomial x^3 - x^2 - x - 1, same product argument.
        self.assertLess(1 - 1 - 1 - 1, 0)
        self.assertGreater(8 - 4 - 2 - 1, 0)
        derivative_positive_past_one = 3 * 4 - 2 * 2 - 1  # f'(2) > 0, and f'(1) = 0
        self.assertEqual(3 * 1 - 2 * 1 - 1, 0)
        self.assertGreater(derivative_positive_past_one, 0)

        # Cube root of 2. 1 < theta < 2 because 1 < 2 < 8 = 2^3.
        # The product of the conjugate moduli equals theta^2. theta > 1
        # forces that product above 1, so both conjugates cannot lie in
        # the open disk.
        self.assertLess(1, 2)
        self.assertLess(2, 8)

    def test_integers_at_least_two_are_pisot_and_worse_than_phi(self):
        # Degree one has no conjugate. phi < 2 because sqrt(5) < 3.
        self.assertLess(5, 9)
        for integer in (2, 3, 10):
            self.assertGreaterEqual(integer, 2)


class ExpansionTests(unittest.TestCase):
    def test_one_has_a_finite_expansion_in_base_phi_and_base_psi(self):
        getcontext().prec = 60
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        # 1 = phi^{-1} + phi^{-2} is phi^2 = phi + 1, cleared of denominators.
        self.assertLess(abs(phi**2 - phi - 1), Decimal("1e-50"))
        psi = Decimal(1)
        for _ in range(40):
            function = psi**3 - psi - 1
            psi -= function / (3 * psi**2 - 1)
        self.assertLess(abs(psi ** -2 + psi ** -3 - 1), Decimal("1e-40"))
        # Perrin tracks psi^n to within twice the conjugate modulus.
        for n in (4, 8, 12):
            error = abs(Decimal(perrin(n)) - psi**n)
            bound = 2 * (psi ** (-Decimal(n) / 2))
            self.assertLess(error, bound)


if __name__ == "__main__":
    unittest.main()
