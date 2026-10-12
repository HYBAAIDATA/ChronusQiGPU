import unittest

from chronus.tribonacci import (
    companion_matrix, n_step_fast_doubling, n_step_fib,
    n_step_pisot_root, tetranacci, tribonacci,
)


def reference(n, k):
    values = [0] * (n - 1) + [1]
    while len(values) <= k:
        values.append(sum(values[-n:]))
    return values[k]


class NStepTests(unittest.TestCase):
    def test_three_independent_paths(self):
        for n in range(2, 9):
            for k in range(100):
                expected = reference(n, k)
                self.assertEqual(n_step_fib(n, k), expected)
                self.assertEqual(n_step_fast_doubling(n, k), expected)

    def test_initial_conditions(self):
        self.assertEqual([tribonacci(k) for k in range(10)], [0, 0, 1, 1, 2, 4, 7, 13, 24, 44])
        self.assertEqual([tetranacci(k) for k in range(8)], [0, 0, 0, 1, 1, 2, 4, 8])

    def test_companion_contract(self):
        self.assertEqual(companion_matrix(3), ((1, 1, 1), (1, 0, 0), (0, 1, 0)))
        self.assertEqual(n_step_fast_doubling(3, 1), 0)

    def test_exact_root_descriptor(self):
        for n in range(2, 20):
            root = n_step_pisot_root(n)
            self.assertEqual(root.polynomial, (1,) + (-1,) * n)
            self.assertEqual(root.isolating_interval, (1, 2))
            for x, expected in ((1, 1 - n), (2, 1)):
                result = 0
                for coefficient in root.polynomial:
                    result = result * x + coefficient
                self.assertEqual(result, expected)

    def test_invalid_inputs(self):
        for function in (n_step_fib, n_step_fast_doubling):
            for n, k in ((1, 0), (3, -1)):
                with self.assertRaises(ValueError):
                    function(n, k)
            with self.assertRaises(TypeError):
                function(3, True)
        with self.assertRaises(ValueError):
            n_step_pisot_root(1)
