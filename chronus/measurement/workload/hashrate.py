"""SHA-256d hashrate — real scans through OpenClPunchHost, backend-labelled.

The host runs the OpenCL kernel when a device exists and falls back to the CPU
scanner when it does not; ``last_dispatch_backend`` reports which surface did
the work. Either way the measurement is real hashing, never assumed.

Invariants:
    HR1: the hashrate is measured, not assumed.
    HR2: the hashrate is a distribution, not a scalar.
    HR3: the measurement includes warmup samples.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...seam.types import Distribution
from .._common import distribution_of


@dataclass
class HashrateMeasurement:
    hps: Distribution
    kernel: str
    device_id: str
    precision: str
    backend: str
    samples: int
    warmup: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hps": self.hps.as_dict(),
            "kernel": self.kernel,
            "device_id": self.device_id,
            "precision": self.precision,
            "backend": self.backend,
            "samples": self.samples,
            "warmup": self.warmup,
        }


def _measure_window(host: Any, window: int, target: int) -> float:
    """One timed scan of ``window`` nonces; returns measured seconds."""
    header = os.urandom(76)
    start = time.perf_counter()
    host.scan_sha256d(header, target, window)
    return time.perf_counter() - start


def measure_hashrate(
    samples: int = 8,
    warmup: int = 2,
    window: int = 4096,
    target: int = 0,
    host: Optional[Any] = None,
) -> HashrateMeasurement:
    """Measure SHA-256d H/s on the punch host.

    ``target=0`` makes every window a miss — the point is throughput, not hits.
    """
    if host is None:
        from ...opencl_host import OpenClPunchHost

        host = OpenClPunchHost()
    for _ in range(max(0, warmup)):
        _measure_window(host, window, target)
    durations = [_measure_window(host, window, target) for _ in range(max(1, samples))]
    hps_samples = [window / d for d in durations if d > 0]
    return HashrateMeasurement(
        hps=distribution_of(hps_samples),
        kernel="sha256d_scan",
        device_id=host.device_name or host.backend,
        precision="uint32",
        backend=host.last_dispatch_backend or host.backend,
        samples=len(hps_samples),
        warmup=max(0, warmup),
    )
