import sys
import unittest
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from scripts.release_gate import _release_status


class ReleaseGateStatusTests(unittest.TestCase):
    def test_pass_requires_every_gate_to_pass(self):
        self.assertEqual(
            _release_status({"logic": {"status": "PASS"}, "hardware": {"status": "PASS"}}),
            "PASS",
        )

    def test_missing_hardware_blocks_release(self):
        self.assertEqual(
            _release_status({"logic": {"status": "PASS"}, "hardware": {"status": "NOT_RUN"}}),
            "BLOCKED",
        )

    def test_failure_takes_precedence_over_missing_hardware(self):
        self.assertEqual(
            _release_status({"logic": {"status": "FAIL"}, "hardware": {"status": "NOT_RUN"}}),
            "FAIL",
        )

    def test_unknown_status_fails_closed(self):
        self.assertEqual(_release_status({"hardware": {"status": "UNAVAILABLE"}}), "FAIL")


if __name__ == "__main__":
    unittest.main()
