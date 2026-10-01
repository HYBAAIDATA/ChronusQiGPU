"""Peak compute — a real dense matmul, timed, on the execution surface.

Invariants:
    CP1: peak compute is measured, not assumed.
    CP2: the precision and the method are declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .._common import now_ns


@dataclass
class ComputeMeasurement:
    operations: int
    duration_ns: int
    tflops: float
    precision: str
    method: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operations": self.operations,
            "duration_ns": self.duration_ns,
            "tflops": self.tflops,
            "precision": self.precision,
            "method": self.method,
        }


def measure_peak_compute(
    n: int = 512,
    precision: str = "fp32",
    repeats: int = 5,
    matmul_fn: Optional[Any] = None,
) -> ComputeMeasurement:
    """Time an n×n dense matmul and report 2n³/ns as TFLOPs.

    ``matmul_fn`` overrides the benchmark body for a device path; otherwise the
    measurement is the host NumPy BLAS path and the method says so.
    """
    dtype = np.float32 if precision == "fp32" else np.float64
    if matmul_fn is None:
        rng = np.random.default_rng(0)
        a = rng.standard_normal((n, n)).astype(dtype)
        b = rng.standard_normal((n, n)).astype(dtype)
        c = np.empty((n, n), dtype=dtype)

        def body() -> None:
            np.matmul(a, b, out=c)

        method = f"host_numpy_matmul_{dtype.__name__}"
    else:

        def body() -> None:
            matmul_fn()

        method = "device_matmul_via_callable"

    body()  # warm
    start = now_ns()
    for _ in range(max(1, int(repeats))):
        body()
    duration_ns = max(1, (now_ns() - start) // max(1, int(repeats)))
    ops = 2 * (n**3)
    return ComputeMeasurement(
        operations=ops,
        duration_ns=duration_ns,
        tflops=float(ops) / float(duration_ns) / 1e3,
        precision=precision,
        method=method,
    )
