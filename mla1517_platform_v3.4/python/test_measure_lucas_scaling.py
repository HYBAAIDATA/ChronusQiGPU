import importlib.util
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

_PLATFORM_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _PLATFORM_ROOT / "scripts" / "measure_lucas_scaling.py"
_SPEC = importlib.util.spec_from_file_location("measure_lucas_scaling", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _module
_SPEC.loader.exec_module(_module)

DIFF1_TARGET = _module.DIFF1_TARGET
LUCAS_PISOT_LADDER = _module.LUCAS_PISOT_LADDER
LiveMeasurementError = _module.LiveMeasurementError
effective_hashrate = _module.effective_hashrate
format_rate = _module.format_rate
load_adapter = _module.load_adapter
parse_endpoint = _module.parse_endpoint


class LiveScalingHarnessTests(unittest.TestCase):
    def test_declared_ladder_is_exact_and_complete(self):
        self.assertEqual(LUCAS_PISOT_LADDER, (10, 12, 15, 18, 20, 31, 50, 76))

    def test_endpoint_parser_requires_host_and_port(self):
        self.assertEqual(parse_endpoint("pool.example:3333", "primary").port, 3333)
        with self.assertRaises(ValueError):
            parse_endpoint("pool.example", "primary")

    def test_hashrate_requires_pool_difficulty_or_target(self):
        with self.assertRaises(LiveMeasurementError):
            effective_hashrate(1, 1_000_000_000, difficulty=None, target=None)

    def test_hashrate_uses_announced_difficulty_as_exact_rational(self):
        rate = effective_hashrate(
            1,
            1_000_000_000,
            difficulty=Decimal("2"),
            target=None,
        )
        self.assertEqual(rate, Fraction(DIFF1_TARGET, 2))
        self.assertEqual(format_rate(rate), format(Decimal(DIFF1_TARGET) / Decimal(2), "f"))

    def test_target_path_is_exact(self):
        target = DIFF1_TARGET // 4
        rate = effective_hashrate(2, 2_000_000_000, difficulty=None, target=target)
        self.assertEqual(rate, Fraction(8 * 1_000_000_000, 2_000_000_000))

    def test_adapter_is_mandatory(self):
        with self.assertRaises(LiveMeasurementError):
            load_adapter("missing_module:factory")

    def test_production_script_has_no_simulation_delay_or_acceptance_increment(self):
        source = _SCRIPT_PATH.read_text()
        self.assertNotIn("time.sleep", source)
        self.assertNotIn("time.sleep", source)
        self.assertNotIn("Simulated", source)
        self.assertIn("response is True", source)
        self.assertIn("OpenCLLadderExecutor", source)


if __name__ == "__main__":
    unittest.main()
