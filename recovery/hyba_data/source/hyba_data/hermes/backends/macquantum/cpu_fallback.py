"""
CPU Fallback Accelerator
=========================

CPU-only fallback when no GPU accelerator is available.

Provides the same interface as GPU accelerators but executes
all operations on CPU using NumPy/PyTorch CPU tensors. This
ensures the system degrades gracefully on hardware without
GPU support.

Performance Characteristics:
    - 10-100x slower than GPU for parallelizable workloads
    - Adequate for development, testing, and small-scale operations
    - Memory limited to system RAM

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Sequence

from core.constants import PHI

from .accelerator_base import AcceleratorBase
from .taxonomy import AcceleratorType, DeviceCapabilities

logger = logging.getLogger(__name__)


class CPUFallbackAccelerator(AcceleratorBase):
    """
    CPU-only fallback when no GPU accelerator is available.

    Provides the same interface as GPU accelerators but executes
    all operations on CPU using NumPy/PyTorch CPU tensors.

    Example:
        >>> accel = CPUFallbackAccelerator()
        >>> result = accel.execute("phi_resonance", [nonce_array])
    """

    def __init__(self) -> None:
        super().__init__()

    @property
    def available(self) -> bool:
        return True  # CPU is always available

    @property
    def accelerator_type(self) -> str:
        return AcceleratorType.CPU_FALLBACK.name

    def _detect_capabilities(self) -> DeviceCapabilities:
        """Detect CPU capabilities."""
        try:
            import psutil

            mem_total = psutil.virtual_memory().total
            mem_available = psutil.virtual_memory().available
        except ImportError:
            mem_total = 16 * (1024**3)  # Assume 16GB
            mem_available = mem_total

        cpu_count = os.cpu_count() or 4

        return DeviceCapabilities(
            accelerator_type=AcceleratorType.CPU_FALLBACK,
            device_name="CPU Fallback",
            memory_total_bytes=mem_total,
            memory_available_bytes=mem_available,
            compute_units=cpu_count,
            bandwidth_gbps=50.0,  # DDR5 approximate
            supports_fp16=False,
            supports_bf16=False,
            supports_tf32=False,
        )

    def _execute_kernel_impl(
        self,
        kernel_name: str,
        inputs: Sequence[Any],
        params: Dict[str, Any],
    ) -> Any:
        """Execute kernel on CPU using NumPy."""
        import numpy as np

        # Convert inputs to numpy
        np_inputs = []
        for inp in inputs:
            if hasattr(inp, "numpy"):
                np_inputs.append(inp.numpy())
            elif isinstance(inp, np.ndarray):
                np_inputs.append(inp)
            else:
                np_inputs.append(np.array(inp, dtype=np.float32))

        if kernel_name == "phi_resonance":
            nonce = np_inputs[0].astype(np.float32)
            alpha = params.get("alpha", PHI**-2)
            beta = params.get("beta", PHI**-3)
            gamma = params.get("gamma", PHI**-4)
            two_pi_over_phi = 2.0 * np.pi / PHI
            pi_over_5 = np.pi / 5.0
            return (
                alpha * np.cos(two_pi_over_phi * nonce)
                + beta * np.sin(two_pi_over_phi * nonce)
                + gamma * np.cos(pi_over_5 * nonce)
            )
        elif kernel_name == "gemm":
            return np.matmul(np_inputs[0], np_inputs[1])
        elif kernel_name == "elementwise":
            op = params.get("op", "phi_scale")
            x = np_inputs[0]
            if op == "phi_scale":
                return x * PHI
            elif op == "phi_normalize":
                return x / PHI
            return x
        elif kernel_name == "reduce":
            op = params.get("op", "sum")
            x = np_inputs[0]
            if op == "sum":
                return np.sum(x, axis=params.get("dim", None))
            elif op == "max":
                return np.max(x, axis=params.get("dim", None))
            elif op == "mean":
                return np.mean(x, axis=params.get("dim", None))
            return np.sum(x)
        else:
            msg = f"Unknown kernel: {kernel_name}"
            raise ValueError(msg)

    def _synchronize_impl(self) -> None:
        """CPU is always synchronous; no-op."""

    def _allocate_impl(self, size_bytes: int) -> Any:
        """Allocate CPU memory as numpy array."""
        import numpy as np

        n_elements = size_bytes // 4
        return np.empty(n_elements, dtype=np.float32)

    def _free_impl(self, handle: Any) -> None:
        """Free CPU array."""
        del handle


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["CPUFallbackAccelerator"]
