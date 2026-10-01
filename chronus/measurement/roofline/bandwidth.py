"""Effective bandwidth — a real buffer copy, timed, on the execution surface.

When an OpenCL device is live the caller may pass a device copy; the default
measures the host surface this code actually runs on (NumPy contiguous copy)
and says so in ``method``.

Invariants:
    BW1: every bandwidth is measured, not assumed.
    BW2: the measurement method is declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .._common import now_ns


@dataclass
class BandwidthMeasurement:
    bytes_transferred: int
    duration_ns: int
    bandwidth_gbps: float
    method: str
    level: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "bytes_transferred": self.bytes_transferred,
            "duration_ns": self.duration_ns,
            "bandwidth_gbps": self.bandwidth_gbps,
            "method": self.method,
            "level": self.level,
        }


def measure_bandwidth(
    size_bytes: int = 64 * 1024 * 1024,
    level: str = "global",
    repeats: int = 10,
    copy_fn: Optional[Any] = None,
) -> BandwidthMeasurement:
    """Time a contiguous copy of ``size_bytes`` and report read+write bytes/s.

    ``copy_fn`` overrides the benchmark body (e.g. a device-side copy); its
    presence does not change the honest accounting: 2 * size moved per copy.
    """
    if copy_fn is None:
        src = np.empty(size_bytes, dtype=np.uint8)
        dst = np.empty_like(src)
        src[:] = 0x5A

        def body() -> None:
            np.copyto(dst, src)

        method = "host_numpy_contiguous_copy"
    else:

        def body() -> None:
            copy_fn()

        method = "device_copy_via_callable"

    body()  # warm the path once before timing
    start = now_ns()
    for _ in range(max(1, int(repeats))):
        body()
    duration_ns = max(1, (now_ns() - start) // max(1, int(repeats)))
    bandwidth_gbps = (2.0 * float(size_bytes)) / float(duration_ns)
    return BandwidthMeasurement(
        bytes_transferred=2 * size_bytes,
        duration_ns=duration_ns,
        bandwidth_gbps=bandwidth_gbps,
        method=method,
        level=level,
    )
