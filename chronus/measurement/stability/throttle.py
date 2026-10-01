"""Throttling detection — real clock sampling where a clock source exists.

Sources tried: Linux ``/sys/.../cur_freq`` cpufreq nodes, then
``/proc/cpuinfo`` MHz. Absent → ``available=False``.

Invariants:
    THR1: throttling is detected by comparing measured clock samples.
"""

from __future__ import annotations

import glob
import re
import time
from typing import Any, Callable, Dict, List, Optional


def _sysfs_clock_mhz() -> Optional[float]:
    paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")
    if not paths:
        return None
    try:
        vals = [int(open(p, encoding="ascii").read().strip()) / 1000.0 for p in paths]
        return sum(vals) / len(vals)
    except (OSError, ValueError):
        return None


def _proc_clock_mhz() -> Optional[float]:
    try:
        with open("/proc/cpuinfo", encoding="ascii") as fh:
            mhz = re.findall(r"cpu MHz\s*:\s*([\d.]+)", fh.read())
        if mhz:
            return sum(float(v) for v in mhz) / len(mhz)
    except OSError:
        return None
    return None


def detect_throttle(
    samples: int = 20,
    period_s: float = 0.1,
    clock_fn: Optional[Callable[[], Optional[float]]] = None,
    max_min_spread_mhz: float = 100.0,
) -> Dict[str, Any]:
    """Sample a real clock ``samples`` times; flag spread above the threshold."""
    reader = clock_fn or (_sysfs_clock_mhz if _sysfs_clock_mhz() is not None else _proc_clock_mhz)
    if reader is None:
        return {
            "available": False,
            "reason": "no clock-frequency surface on this host",
            "unknown": ["clock_mhz"],
        }
    readings: List[float] = []
    for _ in range(max(2, samples)):
        v = reader()
        if v is not None:
            readings.append(v)
        time.sleep(period_s)
    if len(readings) < 2:
        return {
            "available": False,
            "reason": "clock source returned fewer than two samples",
            "unknown": ["clock_mhz"],
        }
    spread = max(readings) - min(readings)
    return {
        "available": True,
        "clock_min_mhz": min(readings),
        "clock_max_mhz": max(readings),
        "clock_mean_mhz": sum(readings) / len(readings),
        "samples": len(readings),
        "throttled": spread > max_min_spread_mhz,
        "method": reader.__name__,
    }
