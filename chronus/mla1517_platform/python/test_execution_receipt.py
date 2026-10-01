import unittest

from chronus.mla1517.mining.execution import MiningExecutionResult


class MiningExecutionReceiptTests(unittest.TestCase):
    def test_cpu_reference_is_truth_labelled_and_measured(self):
        result = MiningExecutionResult.observed(
            requested_backend="cpu_reference",
            actual_backend="cpu_reference",
            device_name=None,
            device_available=False,
            hardware_execution=False,
            hashes_computed=100,
            elapsed_seconds=2.0,
        )
        self.assertEqual(result.truth_class, "measured_cpu_reference")
        self.assertEqual(result.measured_hashrate, 50.0)
        self.assertFalse(result.hardware_execution)

    def test_missing_hardware_is_not_relabelled(self):
        result = MiningExecutionResult.observed(
            requested_backend="mla1517_chronus",
            actual_backend=None,
            device_name=None,
            device_available=False,
            hardware_execution=False,
            hashes_computed=0,
            elapsed_seconds=1.0,
            degraded=True,
        )
        self.assertEqual(result.truth_class, "unavailable")
        self.assertEqual(result.measured_hashrate, 0.0)

    def test_hardware_claim_requires_device_evidence(self):
        with self.assertRaises(ValueError):
            MiningExecutionResult(
                requested_backend="mla1517_chronus",
                selected_backend="mla1517_chronus",
                actual_backend="mla1517_chronus",
                device_name=None,
                device_available=False,
                hardware_execution=True,
                degraded=False,
                fallback_used=False,
                hashes_computed=1,
                elapsed_seconds=1.0,
                measured_hashrate=1.0,
                truth_class="measured_hardware",
            )


if __name__ == "__main__":
    unittest.main()
