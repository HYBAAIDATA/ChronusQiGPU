"""Physical Chronus tensor throughput measurement.

This module measures the existing :mod:`chronus.tensor_compute` OpenCL path.
It does not replace the host NumPy reference benchmark and does not add a CPU
fallback. If no Chronus GPU/accelerator runtime is available, callers receive
the runtime's fail-closed exception and can record the stage as unavailable.

The reported throughput is end-to-end for ``ChronusTensorRuntime.execute``:
buffer creation/copies, kernel dispatch, result copy, and queue completion are
all inside the timed interval. Numerical output is independently checked
against NumPy before the measurement is accepted.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ...seam.types import Distribution
from .._common import distribution_of


@dataclass
class DeviceTensorMeasurement:
    gflops: Distribution
    tflops: Distribution
    operation: str
    shape: Tuple[int, int]
    precision: str
    bytes_transferred: int
    method: str
    backend: str
    device_id: str
    warmup: int
    verified: bool
    verification_max_abs_error: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "gflops": self.gflops.as_dict(),
            "tflops": self.tflops.as_dict(),
            "operation": self.operation,
            "shape": list(self.shape),
            "precision": self.precision,
            "bytes_transferred": self.bytes_transferred,
            "method": self.method,
            "backend": self.backend,
            "device_id": self.device_id,
            "warmup": self.warmup,
            "verified": self.verified,
            "verification_max_abs_error": self.verification_max_abs_error,
        }


def measure_device_tensor_matmul(
    shape: Tuple[int, int] = (256, 256),
    *,
    repeats: int = 16,
    warmup: int = 2,
    runtime: Optional[Any] = None,
    rtol: float = 1e-4,
    atol: float = 1e-4,
) -> DeviceTensorMeasurement:
    """Measure the physical Chronus OpenCL matmul path.

    ``runtime`` is injectable for software-contract tests. Production callers
    omit it and therefore use ``chronus.tensor_compute.get_runtime()``, which
    accepts only an OpenCL GPU/accelerator and has no CPU fallback.
    """
    m, n = (int(shape[0]), int(shape[1]))
    if m <= 0 or n <= 0:
        raise ValueError("tensor shape dimensions must be positive")
    repeats = max(1, int(repeats))
    warmup = max(0, int(warmup))

    if runtime is None:
        from ...tensor_compute import get_runtime

        runtime = get_runtime()

    rng = np.random.default_rng(0)
    a = rng.standard_normal((m, n)).astype(np.float32)
    b = rng.standard_normal((n, m)).astype(np.float32)
    expected = np.matmul(a, b).astype(np.float32, copy=False)

    def _execute() -> np.ndarray:
        out = runtime.execute(
            "matmul",
            [a, b],
            [a.shape, b.shape],
            (m, m),
        )
        return np.asarray(out, dtype=np.float32)

    for _ in range(warmup):
        _execute()

    durations_ns = []
    result: Optional[np.ndarray] = None
    for _ in range(repeats):
        started = time.perf_counter_ns()
        result = _execute()
        durations_ns.append(time.perf_counter_ns() - started)

    if result is None:
        raise RuntimeError("Chronus tensor measurement produced no result")
    if result.shape != expected.shape:
        raise RuntimeError(
            f"Chronus tensor result shape {result.shape} != reference {expected.shape}"
        )

    delta = np.abs(result.astype(np.float64) - expected.astype(np.float64))
    max_abs_error = float(delta.max(initial=0.0))
    verified = bool(np.allclose(result, expected, rtol=float(rtol), atol=float(atol)))
    if not verified:
        raise RuntimeError(
            "Chronus tensor device result failed NumPy verification "
            f"(max_abs_error={max_abs_error:.9g})"
        )

    flops = 2 * m * n * m
    gflops_samples = [flops / d_ns for d_ns in durations_ns if d_ns > 0]
    if not gflops_samples:
        raise RuntimeError("Chronus tensor measurement produced no positive duration")
    tflops_samples = [value / 1000.0 for value in gflops_samples]
    bytes_moved = (m * n + n * m + m * m) * np.dtype(np.float32).itemsize

    return DeviceTensorMeasurement(
        gflops=distribution_of(gflops_samples),
        tflops=distribution_of(tflops_samples),
        operation="matmul",
        shape=(m, n),
        precision="fp32",
        bytes_transferred=bytes_moved,
        method="chronus_opencl_end_to_end_matmul_f32",
        backend="chronus-opencl",
        device_id=str(getattr(runtime, "device_id", "") or ""),
        warmup=warmup,
        verified=True,
        verification_max_abs_error=max_abs_error,
    )
