"""Applications of the plastic number that can be decided exactly.

Padovan is a zero-free companion and tightens the odd-part bound.
The Perrin trace is not, because the minimal polynomial has no x^2 term.
The plastic turn does not beat the golden turn on a sphere.
"""

from __future__ import annotations

from fractions import Fraction
import math
import unittest


def padovan(n: int) -> int:
    a, b, c = 1, 1, 1
    if n < 3:
        return (a, b, c)[n]
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b
    return c


def perrin(n: int) -> int:
    a, b, c = 3, 0, 2
    if n < 3:
        return (a, b, c)[n]
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b
    return c


def lucas(n: int) -> int:
    if n == 0:
        return 2
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def second_pisot_trace(n: int) -> int:
    """Power sums of x^4 - x^3 - 1. Positive for every n >= 1."""
    values = [4, 1, 1, 1]
    while len(values) <= n:
        values.append(values[-1] + values[-4])
    return values[n]


def compositions(n: int) -> int:
    """Compositions of n with parts in {2, 3}. The empty composition is 1."""
    if n == 0:
        return 1
    ways = [0] * (n + 1)
    ways[0] = 1
    for total in range(1, n + 1):
        if total >= 2:
            ways[total] += ways[total - 2]
        if total >= 3:
            ways[total] += ways[total - 3]
    return ways[n]


def odd_part(value: int) -> int:
    value = abs(value)
    if value == 0:
        return 0
    while value % 2 == 0:
        value //= 2
    return value


class CompanionTests(unittest.TestCase):
    def test_padovan_stays_positive_and_perrin_dies_at_one(self):
        self.assertEqual([padovan(n) for n in range(3)], [1, 1, 1])
        for n in range(3, 40):
            self.assertEqual(padovan(n), padovan(n - 2) + padovan(n - 3))
            self.assertGreater(padovan(n), 0)
        self.assertEqual(perrin(1), 0)
        self.assertEqual(second_pisot_trace(1), 1)
        for n in range(1, 30):
            self.assertGreater(second_pisot_trace(n), 0)

    def test_compositions_match_padovan_after_the_structural_zero(self):
        self.assertEqual(compositions(1), 0)
        for n in range(2, 25):
            self.assertEqual(compositions(n), padovan(n - 2))

    def test_padovan_odd_part_telescopes_and_beats_lucas(self):
        # a_1 = 1, so the product of ratios is 1/P_{k+1} with no cancellation.
        self.assertEqual(padovan(1), 1)
        for k in (5, 10, 20, 40):
            product = Fraction(1)
            for n in range(1, k + 1):
                product *= Fraction(padovan(n), padovan(n + 1))
            self.assertEqual(product, Fraction(1, padovan(k + 1)))
            self.assertEqual(odd_part(product.denominator), odd_part(padovan(k + 1)))
        self.assertLess(odd_part(padovan(60)).bit_length(), odd_part(lucas(60)).bit_length())
        self.assertLess(
            odd_part(padovan(60)).bit_length(),
            odd_part(second_pisot_trace(60)).bit_length(),
        )
        self.assertLess(
            odd_part(second_pisot_trace(60)).bit_length(),
            odd_part(lucas(60)).bit_length(),
        )
        self.assertEqual(odd_part(lucas(11)), 199)
        self.assertEqual(padovan(11), 16)
        self.assertEqual(odd_part(padovan(11)), 1)


class SphereApplicationTests(unittest.TestCase):
    def test_plastic_turn_is_not_the_sphere_packing(self):
        golden = sphere_nn_cv(1.0 / (((1.0 + math.sqrt(5.0)) / 2.0) ** 2), 200)
        plastic_root = 1.324717957244746
        plastic = sphere_nn_cv(1.0 / (plastic_root ** 2), 200)
        self.assertLess(golden, plastic)
        self.assertLess(golden, 0.05)
        self.assertGreater(plastic, 0.15)


def sphere_nn_cv(turn: float, count: int) -> float:
    points = []
    for index in range(count):
        z = 1.0 - 2.0 * (index + 0.5) / count
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        theta = 2.0 * math.pi * ((index * turn) % 1.0)
        points.append((radius * math.cos(theta), radius * math.sin(theta), z))
    nearest = []
    for index, origin in enumerate(points):
        best = None
        for other_index, other in enumerate(points):
            if other_index == index:
                continue
            distance = math.dist(origin, other)
            if best is None or distance < best:
                best = distance
        nearest.append(best)
    mean = sum(nearest) / len(nearest)
    variance = sum((value - mean) ** 2 for value in nearest) / len(nearest)
    return math.sqrt(variance) / mean


if __name__ == "__main__":
    unittest.main()
