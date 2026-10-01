"""Tensor contraction throughput — real NumPy contraction, timed.

Invariants:
    TM1: tensor GFLOPS is measured.
    TM2: the shape and precision are declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

from ...seam.types import Distribution
from .._common import distribution_of, timed_calls


@dataclass
class TensorMeasurement:
    gflops: Distribution
    operation: str
    shape: Tuple[int, int]
    precision: str
    bytes_transferred: int
    method: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "gflops": self.gflops.as_dict(),
            "operation": self.operation,
            "shape": list(self.shape),
            "precision": self.precision,
            "bytes_transferred": self.bytes_transferred,
            "method": self.method,
        }


def measure_tensor_contraction(
    shape: Tuple[int, int] = (256, 256),
    precision: str = "fp32",
    repeats: int = 16,
) -> TensorMeasurement:
    """n×n matmul: 2n³ flops over 3n² elements moved."""
    m, n = shape
    dtype = np.float32 if precision == "fp32" else np.float64
    rng = np.random.default_rng(0)
    a = rng.standard_normal((m, n)).astype(dtype)
    b = rng.standard_normal((n, m)).astype(dtype)
    c = np.empty((m, m), dtype=dtype)

    durations_ns = timed_calls(lambda: np.matmul(a, b, out=c), repeats)
    flops = 2 * m * n * m
    gflops_samples = [flops / d_ns for d_ns in durations_ns if d_ns > 0]
    bytes_moved = (m * n + n * m + m * m) * np.dtype(dtype).itemsize
    return TensorMeasurement(
        gflops=distribution_of(gflops_samples),
        operation="contraction",
        shape=shape,
        precision=precision,
        bytes_transferred=bytes_moved,
        method=f"host_numpy_matmul_{dtype.__name__}",
    )
