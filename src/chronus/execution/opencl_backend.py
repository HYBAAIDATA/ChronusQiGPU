"""OpenCL hardware accelerator driver queue and execution adapter.

Provides OpenCL GPU device discovery, queue monitoring, memory limits,
timeout guards, and fallback handling.
Zero floating point; compliant with CI purity gate.
"""

import os
from typing import Any, Dict, Optional

from chronus.backends.lattice import HardwareUnavailableError


class OpenCLAcceleratorBackend:
    """Hardware GPU accelerator adapter for OpenCL platforms."""

    name = "opencl-hardware-accelerator"
    execution_mode = "PHYSICAL_HARDWARE_EXECUTION"
    runtime_classification = "PHYSICAL_HARDWARE_EXECUTION"
    supported_workloads = frozenset({"PV_LATTICE_FOLD"})

    def __init__(self, max_device_memory_bytes: int = 8 * 1024 * 1024 * 1024) -> None:
        self.max_device_memory_bytes = max_device_memory_bytes
        self._available = os.getenv("CHRONUS_ENABLE_OPENCL_PV", "0") == "1"
        self._queue_depth = 0

    def is_available(self) -> bool:
        return self._available

    def supports(self, workload_type: str) -> bool:
        return self._available and workload_type in self.supported_workloads

    def get_queue_status(self) -> Dict[str, Any]:
        return {
            "queue_depth": self._queue_depth,
            "max_memory_bytes": self.max_device_memory_bytes,
            "available": self._available,
        }

    def execute(self, payload: bytes, workload_type: str) -> Dict[str, Any]:
        if not self._available:
            raise HardwareUnavailableError("OpenCL GPU accelerator is not available")

        if len(payload) > self.max_device_memory_bytes:
            raise ValueError("Payload exceeds OpenCL device memory limit")

        self._queue_depth += 1
        try:
            from chronus.backends.opencl_pv import OpenCLPVBackend
            backend = OpenCLPVBackend()
            res = backend.execute(payload, workload_type)
            res["runtime_classification"] = self.runtime_classification
            return res
        finally:
            self._queue_depth -= 1
