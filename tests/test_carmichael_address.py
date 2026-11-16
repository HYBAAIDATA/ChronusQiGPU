"""Carmichael primitive-divisor address uniqueness."""

from __future__ import annotations

import unittest

from chronus.math.carmichael_address import (
    address_of,
    fib,
    primitive_divisor,
    self_test,
)


class CarmichaelAddressTests(unittest.TestCase):
    def test_self_test(self) -> None:
        self_test()

    def test_floor_and_known_values(self) -> None:
        self.assertIsNone(primitive_divisor(12))
        self.assertEqual(primitive_divisor(13), 233)
        with self.assertRaises(ValueError):
            address_of(12)
        self.assertEqual(address_of(13), 233)

    def test_fib_basis(self) -> None:
        self.assertEqual([fib(i) for i in range(8)], [0, 1, 1, 2, 3, 5, 8, 13])


if __name__ == "__main__":
    unittest.main()
