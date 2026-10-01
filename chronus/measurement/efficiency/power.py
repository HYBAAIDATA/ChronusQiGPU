"""Power draw — probed from real sensor surfaces; absent sensors are declared.

Sources tried, in order:
    1. Linux RAPL sysfs (``/sys/class/powercap``) — joule counters, timed deltas.
    2. ``nvidia-smi --query-gpu=power.draw`` — a real watt reading.
    3. Nothing else: ``available=False`` and the source list is reported.

Invariants:
    PW1: power is measured, not estimated.
    PW2: the measurement method is declared.
"""

from __future__ import annotations

import glob
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...seam.types import Distribution
from .._common import distribution_of


@dataclass
class PowerMeasurement:
    watts: Optional[Distribution]
    sample_period_ms: int
    method: str
    available: bool
    sources_tried: List[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "watts": self.watts.as_dict() if self.watts else None,
            "sample_period_ms": self.sample_period_ms,
            "method": self.method,
            "available": self.available,
            "sources_tried": list(self.sources_tried),
            "reason": self.reason,
        }


def _rapl_uj() -> Optional[float]:
    paths = glob.glob("/sys/class/powercap/*/energy_uj")
    if not paths:
        return None
    try:
        return sum(int(open(p, encoding="ascii").read().strip()) for p in paths)
    except OSError:
        return None


def _nvidia_smi_w() -> Optional[float]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return float(out.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError):
        return None
    return None


def measure_power(duration_s: float = 2.0, period_ms: int = 100) -> PowerMeasurement:
    """Sample real power sensors for ``duration_s``; unavailable if none exist."""
    tried: List[str] = []
    samples: List[float] = []
    method = ""

    rapl0 = _rapl_uj()
    if rapl0 is not None:
        method = "rapl_energy_uj_delta"
        tried.append("rapl")
        deadline = time.monotonic() + duration_s
        prev_uj, prev_t = rapl0, time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(period_ms / 1000.0)
            cur_uj, cur_t = _rapl_uj(), time.monotonic()
            if cur_uj is None:
                break
            dt = cur_t - prev_t
            if dt > 0 and cur_uj >= prev_uj:
                samples.append((cur_uj - prev_uj) / 1e6 / dt)
            prev_uj, prev_t = cur_uj, cur_t
    else:
        tried.append("rapl(absent)")

        w = _nvidia_smi_w()
        tried.append("nvidia-smi" if w is not None else "nvidia-smi(absent)")
        if w is not None:
            method = "nvidia-smi_power_draw"
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline:
                reading = _nvidia_smi_w()
                if reading is not None:
                    samples.append(reading)
                time.sleep(period_ms / 1000.0)

    if not samples:
        return PowerMeasurement(
            watts=None,
            sample_period_ms=period_ms,
            method="unavailable",
            available=False,
            sources_tried=tried,
            reason="no power sensor surface on this host",
        )
    return PowerMeasurement(
        watts=distribution_of(samples),
        sample_period_ms=period_ms,
        method=method,
        available=True,
        sources_tried=tried,
    )
