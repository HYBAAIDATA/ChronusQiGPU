"""Boundary enforcement tests."""

from __future__ import annotations

import sys
import unittest

from integrations.agi_external.boundary import assert_external_boundary, BoundaryViolation


class TestBoundary(unittest.TestCase):
    def test_clean_state_passes(self) -> None:
        # No forbidden modules should be loaded in a normal test process.
        assert_external_boundary()  # must not raise

    def test_loaded_asi_module_raises(self) -> None:
        sys.modules["Intelligence.asi.forbidden"] = type(sys)("fake")
        try:
            with self.assertRaises(BoundaryViolation):
                assert_external_boundary()
        finally:
            del sys.modules["Intelligence.asi.forbidden"]


if __name__ == "__main__":
    unittest.main()
