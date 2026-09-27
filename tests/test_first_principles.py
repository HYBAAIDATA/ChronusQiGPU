"""First-principles checks for the KAM, packing, QMC, and overhead probes.

Exact claims use Fraction or int equality. Diagnostic floats are compared
with explicit inequalities that were measured, never with a disguised
approximation of an algebraic identity.
"""

from __future__ import annotations

import math
import unittest
from decimal import Decimal
from fractions import Fraction

import numpy as np

from aethel.overhead import price_addresses, price_exact_generator
from kellogg.first_principles import (
    GOLDEN_KAM_CRITICAL_K,
    action_variance,
    additive_recurrence,
    bitwise_word,
    circle_gaps,
    circle_gaps_exact,
    covering_excess,
    elliptic_island_residue,
    exact_fractional,
    fibonacci_lattice,
    fibonacci_number,
    float_fractional,
    generalized_golden,
    golden_angle_degrees,
    golden_ratio,
    golden_turn,
    greene_residue,
    grid_occupancy_std,
    half_interval_count,
    integrate,
    maximal_lyapunov,
    morton_decode,
    morton_encode,
    plastic_number,
    plastic_powers_dependent,
    rational_saturated_excess,
    residue_from_trace,
    row_major_address,
    shear_monodromy,
)


def _fibonacci_pair(index: int) -> tuple[int, int]:
    """Period F_{index+1} and winding F_index, so the ratio tends to 1/φ."""
    return fibonacci_number(index + 1), fibonacci_number(index)


class KamDiagnosticTests(unittest.TestCase):
    def test_integrable_shear_has_residue_zero(self):
        for period in (1, 8, 13, 34, 144):
            monodromy = shear_monodromy(period)
            self.assertEqual(monodromy, ((1, period), (0, 1)))
            trace = monodromy[0][0] + monodromy[1][1]
            self.assertEqual(trace, 2)
            self.assertEqual(residue_from_trace(trace), Fraction(0))

    def test_lyapunov_vanishes_on_the_integrable_map_and_not_in_chaos(self):
        short = maximal_lyapunov(0.0, 0.2, 0.3, 500)
        long = maximal_lyapunov(0.0, 0.2, 0.3, 20000)
        self.assertLess(long, short)
        self.assertLess(long, 0.001)
        self.assertLess(maximal_lyapunov(0.5, 0.2, golden_turn(), 8000), 0.01)
        self.assertGreater(maximal_lyapunov(5.0, 0.2, 0.3, 3000), 0.5)

    def test_greene_residue_collapses_below_critical_and_explodes_above(self):
        below = []
        for index in range(5, 11):
            period, winding = _fibonacci_pair(index)
            # F_{n+1} is the period, F_n the winding: rotation → 1/φ.
            residue, closure = greene_residue(0.5, period, winding)
            self.assertLess(closure, 1e-8)
            self.assertLess(abs(residue), 0.25)
            below.append(abs(residue))
        self.assertLess(below[-1], 1e-9)
        self.assertLess(below[-1], below[0])

        above = []
        for index in range(5, 9):
            period, winding = _fibonacci_pair(index)
            residue, closure = greene_residue(1.5, period, winding)
            self.assertLess(closure, 1e-8)
            above.append(abs(residue))
        self.assertGreater(above[0], 0.25)
        self.assertGreater(above[-1], above[0])
        self.assertGreater(above[-1], 10.0)

    def test_critical_golden_residues_sit_on_the_quarter_band(self):
        for index in range(6, 12):
            period, winding = _fibonacci_pair(index)
            residue, closure = greene_residue(GOLDEN_KAM_CRITICAL_K, period, winding)
            self.assertLess(closure, 1e-8)
            self.assertGreater(abs(residue), 0.24)
            self.assertLess(abs(residue), 0.26)

    def test_mode_lock_residue_does_not_follow_the_torus(self):
        # std(p) is small on both the island and the torus, which is why it
        # cannot tell them apart. The residues can.
        torus_variance = action_variance(0.5, 0.2, golden_turn(), 2000)
        island_variance = action_variance(0.5, 0.5, 0.02, 2000)
        self.assertLess(math.sqrt(torus_variance), 0.05)
        self.assertLess(math.sqrt(island_variance), 0.05)
        self.assertEqual(elliptic_island_residue(0.5), 0.125)
        period, winding = _fibonacci_pair(10)
        residue, _closure = greene_residue(0.5, period, winding)
        self.assertLess(abs(residue), abs(elliptic_island_residue(0.5)))

    def test_action_variance_saturates_on_a_torus_and_grows_in_chaos(self):
        self.assertEqual(action_variance(0.0, 0.2, golden_turn(), 64), 0.0)
        early = action_variance(0.5, 0.2, golden_turn(), 200)
        late = action_variance(0.5, 0.2, golden_turn(), 20000)
        self.assertLess(late / early, 2.0)
        chaotic_early = action_variance(2.5, 0.2, golden_turn(), 200)
        chaotic_late = action_variance(2.5, 0.2, golden_turn(), 20000)
        self.assertGreater(chaotic_late, 10.0 * chaotic_early)


class PackingTests(unittest.TestCase):
    def test_rational_137_saturates_and_golden_excess_stays_bounded(self):
        turn = Fraction(137, 360)
        self.assertEqual(circle_gaps_exact(turn, 360), (Fraction(1, 360), Fraction(1, 360)))
        maximum, _minimum = circle_gaps_exact(turn, 720)
        self.assertEqual(maximum, Fraction(1, 360))
        for count in (360, 1000, 10000):
            self.assertEqual(
                rational_saturated_excess(137, 360, count),
                Fraction(count, 360),
            )
            measured, _min_gap = circle_gaps_exact(turn, count)
            self.assertEqual(count * measured, Fraction(count, 360))
        golden = golden_turn()
        for count in (1000, 10_000, 100_000):
            self.assertLess(covering_excess(golden, count), 2.0)
            self.assertGreater(covering_excess(137.0 / 360.0, count), count / 360.0 - 1e-6)

    def test_coarse_grid_ties_while_continuous_gaps_do_not(self):
        golden = golden_turn()
        rational = 137.0 / 360.0
        self.assertEqual(grid_occupancy_std(golden, 50, 20), grid_occupancy_std(rational, 50, 20))
        golden_span = circle_gaps(golden, 50)
        rational_span = circle_gaps(rational, 50)
        self.assertLess(golden_span[0] - golden_span[1], rational_span[0] - rational_span[1])

    def test_golden_angle_is_not_137(self):
        degrees = golden_angle_degrees()
        self.assertGreater(degrees, 137.5)
        self.assertLess(degrees, 137.52)
        self.assertNotEqual(round(degrees, 1), 137.0)


class QmcTests(unittest.TestCase):
    def test_generalized_golden_family(self):
        phi = generalized_golden(1)
        self.assertAlmostEqual(phi, golden_ratio(), places=12)
        self.assertAlmostEqual(phi * phi - phi - 1.0, 0.0, places=12)
        psi = plastic_number()
        self.assertAlmostEqual(psi, generalized_golden(2), places=12)
        self.assertAlmostEqual(psi**3 - psi - 1.0, 0.0, places=12)
        cube = generalized_golden(3)
        self.assertAlmostEqual(cube**4 - cube - 1.0, 0.0, places=12)
        self.assertTrue(plastic_powers_dependent())

    def test_three_plastic_powers_do_not_fill_the_cube(self):
        psi = plastic_number()
        alphas = (1.0 / psi, 1.0 / psi**2, 1.0 / psi**3)
        points = np.mod(np.arange(4000)[:, None] * np.array(alphas), 1.0)
        estimate = float(np.mean(np.all(points < 0.5, axis=1)))
        # The dependence ψ^{-2} + ψ^{-3} = 1 pins the error near 1/8.
        self.assertGreater(abs(estimate - 0.125), 0.1)

    def test_cube_generator_beats_monte_carlo_and_golden_half_interval_is_exact(self):
        points = additive_recurrence(4000, 3)
        error = abs(float(np.mean(np.all(points < 0.5, axis=1))) - 0.125)
        monte_carlo = []
        for seed in range(25):
            draw = np.random.default_rng(seed).random((4000, 3))
            monte_carlo.append(abs(float(np.mean(np.all(draw < 0.5, axis=1))) - 0.125))
        self.assertLess(error, float(np.median(monte_carlo)))

        alpha = 1.0 / golden_ratio()
        for count in (10, 50, 100, 1000, 4096):
            hits = half_interval_count(alpha, count)
            self.assertLessEqual(abs(hits - count / 2.0), 1.0)

    def test_fibonacci_lattice_is_exact_and_beats_monte_carlo_on_a_smooth_integrand(self):
        points = fibonacci_lattice(18)
        modulus = fibonacci_number(18)
        step = fibonacci_number(17)
        self.assertEqual(len(points), modulus)
        for k, point in enumerate(points):
            self.assertEqual(point[0], Fraction(k, modulus))
            self.assertEqual(point[1], Fraction((k * step) % modulus, modulus))
        array = np.asarray([(float(x), float(y)) for x, y in points], dtype=float)
        error = abs(integrate(array, lambda rows: rows[:, 0] * rows[:, 1]) - 0.25)
        monte_carlo = []
        for seed in range(21):
            draw = np.random.default_rng(seed).random((modulus, 2))
            monte_carlo.append(abs(float(np.mean(draw[:, 0] * draw[:, 1])) - 0.25))
        self.assertLess(error, float(np.median(monte_carlo)))

    def test_singular_boundary_weight_beats_the_monte_carlo_median(self):
        alpha = 1.0 / golden_ratio()

        def quasi_error(count: int) -> float:
            xs = np.array([((k + 1) * alpha) % 1.0 for k in range(count)])
            return abs(float(np.mean(1.0 / np.sqrt(xs))) - 2.0)

        for count in (1000, 10000):
            monte_carlo = []
            for seed in range(30):
                draw = np.random.default_rng(seed).random(count)
                monte_carlo.append(abs(float(np.mean(1.0 / np.sqrt(draw))) - 2.0))
            self.assertLess(quasi_error(count), float(np.median(monte_carlo)))


class OverheadTests(unittest.TestCase):
    def test_modular_fraction_matches_bitwise_and_float_drifts(self):
        modulus = fibonacci_number(24)
        numerator = fibonacci_number(23)
        for count in (0, 1, 17, 10**6, 2**40 + 3):
            witnessed = exact_fractional(count, numerator, modulus)
            self.assertEqual(witnessed.denominator <= modulus, True)
            self.assertEqual(
                witnessed,
                Fraction((count * numerator) % modulus, modulus),
            )
        bits = 16
        multiplier = 40503  # odd, so multiplication mod 2^16 is a bijection
        for count in range(0, 300):
            self.assertEqual(
                bitwise_word(count, multiplier, bits),
                (count * multiplier) % (1 << bits),
            )
        # 2^53 + 17 is not the integer Python float thinks it is multiplying.
        large = 2**53 + 17
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        exact = (Decimal(large) * phi) % 1
        drifted = Decimal(float_fractional(large, (1.0 + math.sqrt(5.0)) / 2.0))
        self.assertGreater(abs(drifted - exact), Decimal("1e-3"))
        # The same index through the Fibonacci modulus does not drift.
        self.assertEqual(
            exact_fractional(large, numerator, modulus),
            Fraction((large * numerator) % modulus, modulus),
        )

    def test_z_order_is_bijective_and_cheaper_than_a_golden_stride(self):
        bits = 8
        width = 1 << bits
        seen = set()
        for y in range(width):
            for x in range(width):
                code = morton_encode(x, y, bits)
                self.assertEqual(morton_decode(code, bits), (x, y))
                seen.add(code)
        self.assertEqual(len(seen), width * width)

        cells = width * width
        stride = 137  # coprime to 256*256? 1024 and 137 are coprime
        self.assertEqual(math.gcd(stride, cells), 1)
        golden_addresses = [(index * stride) % cells for index in range(cells)]
        morton_addresses = []
        for code in range(cells):
            x, y = morton_decode(code, bits)
            morton_addresses.append(row_major_address(x, y, width))
        self.assertEqual(set(golden_addresses), set(morton_addresses))
        golden_cost = price_addresses(golden_addresses, label="golden-stride")
        morton_cost = price_addresses(morton_addresses, label="z-order")
        self.assertLess(morton_cost.miss_cost, golden_cost.miss_cost)
        self.assertEqual(morton_cost.memory_touches, golden_cost.memory_touches)

    def test_ledger_does_not_change_the_sample(self):
        modulus = fibonacci_number(18)
        numerator = fibonacci_number(17)
        before = exact_fractional(123456, numerator, modulus)
        ledger = price_exact_generator(123456)
        after = exact_fractional(123456, numerator, modulus)
        self.assertEqual(before, after)
        self.assertEqual(ledger.arithmetic_ops, 2 * 123456)
        self.assertEqual(ledger.miss_cost, 0)
        self.assertEqual(ledger.memory_touches, 123456)


if __name__ == "__main__":
    unittest.main()
