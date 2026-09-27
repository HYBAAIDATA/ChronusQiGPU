"""Executable behavioral tests for complete Turing nonce scheduling."""
from __future__ import annotations

import unittest

from turing_core import (
    TuringScheduleError,
    complete_nonce_schedule,
    extended_nonce_schedule,
    validate_schedule,
)


class TuringCoreTests(unittest.TestCase):
    def test_complete_schedule_is_a_permutation(self) -> None:
        for window in (0, 1, 2, 32, 257, 4096):
            schedule = complete_nonce_schedule(window, seed=12345)
            self.assertEqual(len(schedule), window)
            self.assertEqual(len(set(schedule)), window)
            self.assertEqual(set(schedule), set(range(window)))

    def test_prefix_never_claims_complete_coverage(self) -> None:
        prefix = extended_nonce_schedule(32, seed=7, cap=8)
        self.assertEqual(len(prefix), 8)
        self.assertEqual(validate_schedule(prefix, 32, require_complete=False), prefix)
        with self.assertRaises(TuringScheduleError):
            validate_schedule(prefix, 32, require_complete=True)

    def test_duplicate_missing_wrapped_and_out_of_range_values_reject(self) -> None:
        with self.assertRaises(TuringScheduleError):
            validate_schedule([0, 0, 2, 3], 4)
        with self.assertRaises(TuringScheduleError):
            validate_schedule([0, 1, 2], 4)
        with self.assertRaises(TuringScheduleError):
            validate_schedule([0, 1, 2, 4], 4)
        with self.assertRaises(TuringScheduleError):
            validate_schedule([0, 1, 2, -1], 4)

    def test_schedule_does_not_silently_wrap_inputs(self) -> None:
        with self.assertRaises(TuringScheduleError):
            validate_schedule([0, 1, 2, 0x100000000], 4)


if __name__ == "__main__":
    unittest.main()
