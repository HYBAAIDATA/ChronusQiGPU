"""Unit and integration tests for Multi-Target Hardware Execution & Dispatch.

Tests:
- HardwareAcceleratorDispatcher backend discovery
- Runtime classification declarations (MATHEMATICAL_EXECUTION, SOFTWARE_EXECUTION, PHYSICAL_HARDWARE_EXECUTION)
- Workload dispatch, timeout guards, and memory boundary checks
- Automatic fault detection and fallback to NativeMathReferenceBackend
"""

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.hardware_dispatcher import (
    MATHEMATICAL_EXECUTION,
    PHYSICAL_HARDWARE_EXECUTION,
    HardwareAcceleratorDispatcher,
)
import pytest

pytestmark = pytest.mark.simulated


class MockFailingAccelerator:
    """Mock physical hardware accelerator that faults on execution."""

    name = "mock_gpu_accelerator"
    supported_workloads = frozenset({"EXACT_Q5_ALGEBRAIC", "MOCK_WORKLOAD"})
    execution_mode = PHYSICAL_HARDWARE_EXECUTION
    runtime_classification = PHYSICAL_HARDWARE_EXECUTION
    max_device_memory_bytes = 1024 * 1024

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def execute(self, payload: bytes, workload_type: str):
        raise HardwareUnavailableError(
            "CUDA device out of memory / ECC double bit error"
        )


class MockHangingAccelerator:
    """Mock physical accelerator that hangs to test watchdog timeout."""

    name = "mock_hanging_accelerator"
    supported_workloads = frozenset({"EXACT_Q5_ALGEBRAIC"})
    execution_mode = PHYSICAL_HARDWARE_EXECUTION
    runtime_classification = PHYSICAL_HARDWARE_EXECUTION
    max_device_memory_bytes = 1024 * 1024

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def execute(self, payload: bytes, workload_type: str):
        time.sleep(2.0)
        return {"status": "hung"}


class TestHardwareDispatcher(unittest.TestCase):
    """Test HardwareAcceleratorDispatcher operations."""

    def setUp(self):
        self.dispatcher = HardwareAcceleratorDispatcher(default_timeout_seconds=5)

    def test_backend_discovery(self):
        """Verify discovery of all default execution targets."""
        backends = self.dispatcher.discover_backends()
        self.assertIn("python-math-reference", backends)
        self.assertIn("opencl-hardware-accelerator", backends)
        self.assertIn("cuda-hardware-accelerator", backends)
        self.assertIn("systemverilog-rtl-simulator", backends)

        ref_info = backends["python-math-reference"]
        self.assertTrue(ref_info["available"])
        self.assertIn("EXACT_Q5_ALGEBRAIC", ref_info["supported_workloads"])

    def test_mathematical_reference_dispatch(self):
        """Dispatching exact Q(√5) arithmetic executes and stamps MATHEMATICAL_EXECUTION."""
        payload = json.dumps(
            {
                "operation": "add",
                "left": {"rational": [3, 1], "sqrt5": [2, 1]},
                "right": {"rational": [1, 1], "sqrt5": [1, 1]},
            }
        ).encode("utf-8")
        receipt = self.dispatcher.dispatch(
            payload=payload,
            workload_type="EXACT_Q5_ALGEBRAIC",
            preferred_backend="python-math-reference",
        )

        self.assertEqual(receipt["backend"], "python-math-reference")
        self.assertEqual(receipt["runtime_classification"], MATHEMATICAL_EXECUTION)
        self.assertFalse(receipt["fallback_occurred"])
        self.assertIn("result", receipt)

    def test_memory_limit_enforcement(self):
        """Payload exceeding memory boundary raises ValueError."""
        # Craft a large payload exceeding small target limit
        small_limit_backend = MockFailingAccelerator()
        small_limit_backend.max_device_memory_bytes = 16  # 16 bytes max
        self.dispatcher.register_backend(small_limit_backend)

        oversized_payload = b"x" * 64
        with self.assertRaises(ValueError) as ctx:
            self.dispatcher.dispatch(
                payload=oversized_payload,
                workload_type="MOCK_WORKLOAD",
                preferred_backend="mock_gpu_accelerator",
            )
        self.assertIn("exceeds target memory limit", str(ctx.exception))

    def test_fault_handling_and_automatic_fallback(self):
        """Hardware failure triggers transparent fallback to NativeMathReferenceBackend."""
        failing_backend = MockFailingAccelerator()
        self.dispatcher.register_backend(failing_backend)

        payload = json.dumps(
            {
                "operation": "multiply",
                "left": {"rational": [2, 1], "sqrt5": [1, 1]},
                "right": {"rational": [2, 1], "sqrt5": [-1, 1]},
            }
        ).encode("utf-8")
        receipt = self.dispatcher.dispatch(
            payload=payload,
            workload_type="EXACT_Q5_ALGEBRAIC",
            preferred_backend="mock_gpu_accelerator",
        )

        # Confirm fallback occurred
        self.assertTrue(receipt["fallback_occurred"])
        self.assertEqual(receipt["backend"], "python-math-reference")
        self.assertIn("ECC double bit error", receipt["fallback_reason"])
        self.assertEqual(
            receipt["result"]["hardware_fallback"]["faulted_target"],
            "mock_gpu_accelerator",
        )

    def test_timeout_guard_fallback(self):
        """A hanging hardware execution times out and falls back to software/math reference."""
        hanging_backend = MockHangingAccelerator()
        self.dispatcher.register_backend(hanging_backend)

        payload = json.dumps(
            {
                "operation": "add",
                "left": {"rational": [1, 1], "sqrt5": [0, 1]},
                "right": {"rational": [0, 1], "sqrt5": [1, 1]},
            }
        ).encode("utf-8")
        receipt = self.dispatcher.dispatch(
            payload=payload,
            workload_type="EXACT_Q5_ALGEBRAIC",
            preferred_backend="mock_hanging_accelerator",
            timeout_seconds=1,  # 1s timeout vs 2s sleep
        )

        self.assertTrue(receipt["fallback_occurred"])
        self.assertEqual(receipt["backend"], "python-math-reference")
        self.assertIn("timed out", receipt["fallback_reason"].lower())


if __name__ == "__main__":
    unittest.main()
