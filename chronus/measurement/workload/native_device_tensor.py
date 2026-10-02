"""Physical Chronus tensor measurements for native CUDA and Metal paths.

The existing OpenCL measurement remains in :mod:`device_tensor`. This module
adds equivalent end-to-end measurement for the native vendor paths without
changing or replacing OpenCL evidence.
"""
from __future__ import annotations

import time
from typing import Any, Optional, Tuple

import numpy as np

from .._common import distribution_of
from .device_tensor import DeviceTensorMeasurement


def measure_native_device_tensor_matmul(
    execution_api: str,
    shape: Tuple[int, int] = (256, 256),
    *,
    repeats: int = 16,
    warmup: int = 2,
    runtime: Optional[Any] = None,
    rtol: float = 1e-4,
    atol: float = 1e-4,
) -> DeviceTensorMeasurement:
    """Measure one native physical Chronus tensor path and verify numerics.

    ``execution_api`` must be ``cuda`` or ``metal``. Production callers omit
    ``runtime`` so the matching fail-closed Chronus native runtime is used.
    Tests may inject a runtime without requiring physical hardware.
    """
    if execution_api not in {"cuda", "metal"}:
        raise ValueError("execution_api must be 'cuda' or 'metal'")

    m, n = (int(shape[0]), int(shape[1]))
    if m <= 0 or n <= 0:
        raise ValueError("tensor shape dimensions must be positive")
    repeats = max(1, int(repeats))
    warmup = max(0, int(warmup))

    if runtime is None:
        from ...native_tensor import get_cuda_runtime, get_metal_runtime

        runtime = get_cuda_runtime() if execution_api == "cuda" else get_metal_runtime()

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
        raise RuntimeError("Chronus native tensor measurement produced no result")
    if result.shape != expected.shape:
        raise RuntimeError(
            f"Chronus native tensor result shape {result.shape} != reference {expected.shape}"
        )

    delta = np.abs(result.astype(np.float64) - expected.astype(np.float64))
    max_abs_error = float(delta.max(initial=0.0))
    verified = bool(np.allclose(result, expected, rtol=float(rtol), atol=float(atol)))
    if not verified:
        raise RuntimeError(
            "Chronus native tensor device result failed NumPy verification "
            f"(backend={execution_api}, max_abs_error={max_abs_error:.9g})"
        )

    flops = 2 * m * n * m
    gflops_samples = [flops / d_ns for d_ns in durations_ns if d_ns > 0]
    if not gflops_samples:
        raise RuntimeError("Chronus native tensor measurement produced no positive duration")
    tflops_samples = [value / 1000.0 for value in gflops_samples]
    bytes_moved = (m * n + n * m + m * m) * np.dtype(np.float32).itemsize

    return DeviceTensorMeasurement(
        gflops=distribution_of(gflops_samples),
        tflops=distribution_of(tflops_samples),
        operation="matmul",
        shape=(m, n),
        precision="fp32",
        bytes_transferred=bytes_moved,
        method=f"chronus_{execution_api}_end_to_end_matmul_f32",
        backend=f"chronus-{execution_api}",
        device_id=str(getattr(runtime, "device_id", "") or ""),
        warmup=warmup,
        verified=True,
        verification_max_abs_error=max_abs_error,
    )


__all__ = ["measure_native_device_tensor_matmul"]
