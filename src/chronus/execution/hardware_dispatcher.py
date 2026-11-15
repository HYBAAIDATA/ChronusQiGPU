"""Multi-target hardware execution dispatcher and acceleration fabric.

Enforces the core architectural paradigm:
"Mathematics first. Representation second. Execution third. Evidence throughout."

Every execution output explicitly declares its runtime classification:
- MATHEMATICAL_EXECUTION
- SOFTWARE_EXECUTION
- PHYSICAL_HARDWARE_EXECUTION

Discovers backends, monitors queues, enforces memory limits and timeout guards,
and provides automatic fallback to software/mathematical reference on physical
hardware fault.
Zero floating point; strictly compliant with CI purity gate.
"""

import concurrent.futures
import logging
import os
import time
from typing import Any, Dict, List, Optional

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.cuda_backend import CUDABackendAdapter
from chronus.execution.native_simd import NativeSIMDBackendAdapter
from chronus.execution.opencl_backend import OpenCLAcceleratorBackend
from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend
from chronus.execution.geometric_galois_miner import GeometricGaloisMinerBackend
from chronus.execution.reference import NativeMathReferenceBackend
from chronus.execution.systemverilog_backend import (
    SystemVerilogHardwareSimulatorBackend,
)

logger = logging.getLogger(__name__)

# Core runtime classifications
MATHEMATICAL_EXECUTION = "MATHEMATICAL_EXECUTION"
SOFTWARE_EXECUTION = "SOFTWARE_EXECUTION"
PHYSICAL_HARDWARE_EXECUTION = "PHYSICAL_HARDWARE_EXECUTION"


class HardwareAcceleratorDispatcher:
    """Dispatches workloads across mathematical, software, and physical hardware surfaces."""

    def __init__(
        self,
        default_timeout_seconds: int = 30,
        enable_simd: bool = False,
    ) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self._reference_backend = NativeMathReferenceBackend()
        self._opencl_backend = OpenCLAcceleratorBackend()
        self._cuda_backend = CUDABackendAdapter()
        self._rtl_backend = SystemVerilogHardwareSimulatorBackend()
        self._opencl_miner_backend = OpenCLSha256dMinerBackend()
        self._geometric_galois_backend = GeometricGaloisMinerBackend()
        self._simd_backend = NativeSIMDBackendAdapter()

        self._backends: Dict[str, Any] = {
            self._reference_backend.name: self._reference_backend,
            self._opencl_backend.name: self._opencl_backend,
            self._cuda_backend.name: self._cuda_backend,
            self._rtl_backend.name: self._rtl_backend,
            self._opencl_miner_backend.name: self._opencl_miner_backend,
            self._geometric_galois_backend.name: self._geometric_galois_backend,
        }
        if enable_simd or os.getenv("CHRONUS_ENABLE_SIMD") == "1":
            self._backends[self._simd_backend.name] = self._simd_backend

    def register_backend(self, backend: Any) -> None:
        """Register an additional hardware or execution backend."""
        self._backends[backend.name] = backend

    def discover_backends(self) -> Dict[str, Dict[str, Any]]:
        """Discover available execution targets and their runtime capabilities."""
        summary = {}
        for name, b in self._backends.items():
            is_avail = b.is_available() if hasattr(b, "is_available") else True
            mode = getattr(b, "execution_mode", SOFTWARE_EXECUTION)
            classification = getattr(b, "runtime_classification", mode)
            summary[name] = {
                "name": name,
                "backend_name": name,
                "available": is_avail,
                "execution_mode": mode,
                "runtime_classification": classification,
                "supported_workloads": sorted(list(b.supported_workloads)),
            }
        return summary

    def discover_accelerators(self) -> List[Any]:
        """Discover accelerators returning target objects with .backend_name attribute."""
        class _DiscoveredTarget:
            def __init__(self, name: str, info: Dict[str, Any]) -> None:
                self.backend_name = name
                self.name = name
                self.available = info["available"]
                self.execution_mode = info["execution_mode"]
                self.runtime_classification = info["runtime_classification"]
                self.supported_workloads = info["supported_workloads"]

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "backend_name": self.backend_name,
                    "name": self.name,
                    "available": self.available,
                    "execution_mode": self.execution_mode,
                    "runtime_classification": self.runtime_classification,
                    "supported_workloads": self.supported_workloads,
                }

        return [_DiscoveredTarget(name, info) for name, info in self.discover_backends().items()]

    def dispatch(
        self,
        payload: bytes,
        workload_type: str,
        preferred_backend: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispatch workload to the optimal target with timeout, memory checks, and fallback."""
        start_ns = time.perf_counter_ns()
        timeout = timeout_seconds or self.default_timeout_seconds
        fallback_occurred = False
        fallback_reason = None

        # 1. Select initial candidate backend
        backend = None
        if preferred_backend and preferred_backend in self._backends:
            candidate = self._backends[preferred_backend]
            if workload_type in candidate.supported_workloads:
                backend = candidate

        if backend is None:
            # Prefer physical hardware accelerator if available and supported
            if self._cuda_backend.supports(workload_type):
                backend = self._cuda_backend
            elif self._opencl_backend.supports(workload_type):
                backend = self._opencl_backend
            elif self._rtl_backend.supports(workload_type):
                backend = self._rtl_backend
            elif self._simd_backend.supports(workload_type):
                backend = self._simd_backend
            else:
                backend = self._reference_backend

        # 2. Execute with timeout guard and memory limits
        target_name = backend.name
        result = None

        try:
            # Memory limit check
            max_bytes = getattr(backend, "max_device_memory_bytes", None) or getattr(
                backend, "max_payload_bytes", 1024 * 1024
            )
            if len(payload) > max_bytes:
                raise ValueError(
                    f"Payload size {len(payload)} exceeds target memory limit {max_bytes}"
                )

            # Execution with watchdog timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(backend.execute, payload, workload_type)
                try:
                    result = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError as exc:
                    raise TimeoutError(
                        f"Execution timed out on {target_name} after {timeout}s"
                    ) from exc

        except (HardwareUnavailableError, TimeoutError, Exception) as fault:
            # 3. Fault handling: automatic fallback to mathematical reference backend
            if (
                target_name != self._reference_backend.name
                and self._reference_backend.supports(workload_type)
            ):
                logger.warning(
                    "Fault on hardware target '%s': %s. Engaging automatic reference fallback.",
                    target_name,
                    fault,
                )
                fallback_occurred = True
                fallback_reason = str(fault)
                result = self._reference_backend.execute(payload, workload_type)
                backend = self._reference_backend
            else:
                raise

        duration_ms = (time.perf_counter_ns() - start_ns) // 1_000_000

        # 4. Enforce runtime classification
        classification = getattr(backend, "runtime_classification", None)
        if not classification:
            if backend.name == self._reference_backend.name:
                if workload_type in ("EXACT_Q5_ALGEBRAIC", "METALLIC_SCALE"):
                    classification = MATHEMATICAL_EXECUTION
                else:
                    classification = SOFTWARE_EXECUTION
            else:
                classification = getattr(backend, "execution_mode", SOFTWARE_EXECUTION)

        # Explicitly declare runtime classification in receipt & result
        receipt = {
            "backend": backend.name,
            "runtime_classification": classification,
            "execution_mode": getattr(backend, "execution_mode", classification),
            "workload_type": workload_type,
            "duration_ms": duration_ms,
            "fallback_occurred": fallback_occurred,
            "fallback_reason": fallback_reason,
            "result": result,
        }

        if isinstance(result, dict):
            result["runtime_classification"] = classification
            result["execution_mode"] = getattr(
                backend, "execution_mode", classification
            )
            if fallback_occurred:
                result["hardware_fallback"] = {
                    "faulted_target": target_name,
                    "reason": fallback_reason,
                }

        return receipt
