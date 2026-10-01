import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "release_gate.py"
SPEC = importlib.util.spec_from_file_location("mla1517_release_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_release_status = MODULE._release_status


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

    def test_policy_check_uses_canonical_behavior_defaults(self):
        self.assertEqual(MODULE._policy_check()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
