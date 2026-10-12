import unittest

from chronus.pisano import fib_mod, pisano_is_period, pisano_period, pisano_table


def recurrence_period(m):
    a, b, steps = 0, 1 % m, 0
    while True:
        a, b = b, (a + b) % m
        steps += 1
        if (a, b) == (0, 1 % m):
            return steps


class PisanoTests(unittest.TestCase):
    def test_differential_periods(self):
        for m in range(1, 501):
            self.assertEqual(pisano_period(m), recurrence_period(m), m)

    def test_prime_bound_is_not_minimum(self):
        self.assertTrue(pisano_is_period(29, 28))
        self.assertEqual(pisano_period(29), 14)

    def test_known_prime_powers(self):
        for k in range(1, 12):
            self.assertEqual(pisano_period(2**k), 3 * 2 ** (k - 1))
        for k in range(1, 7):
            self.assertEqual(pisano_period(5**k), 20 * 5 ** (k - 1))

    def test_modular_recurrence(self):
        for m in (1, 2, 17, 29, 256):
            a, b = 0, 1
            for n in range(300):
                self.assertEqual(fib_mod(n, m), a % m)
                a, b = b, a + b

    def test_large_modular_index(self):
        n = 2**64 - 1
        self.assertEqual(fib_mod(n, 100), fib_mod(n % pisano_period(100), 100))

    def test_table(self):
        self.assertEqual(pisano_table(0), {})
        self.assertEqual(pisano_table(5), {1: 1, 2: 3, 3: 8, 4: 6, 5: 20})

    def test_invalid_inputs(self):
        for m in (0, -1):
            with self.assertRaises(ValueError):
                pisano_period(m)
        for m in (True, 2.0, "2"):
            with self.assertRaises(TypeError):
                pisano_period(m)
        with self.assertRaises(ValueError):
            fib_mod(-1, 3)
        with self.assertRaises(ValueError):
            pisano_is_period(3, 0)
        with self.assertRaises(TypeError):
            fib_mod(True, 3)
