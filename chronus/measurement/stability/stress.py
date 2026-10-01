"""Sustained-load stability — repeated real measurements over a duration.

Invariants:
    STR1: the stress test runs for the declared duration.
    STR2: the degradation is computed from the first and final measurements.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict


def run_stress_test(
    measure_fn: Callable[[], float],
    duration_s: float = 10.0,
    min_samples: int = 3,
) -> Dict[str, Any]:
    """Call ``measure_fn`` (returns a rate) until ``duration_s`` elapses.

    The caller supplies the measured quantity — e.g. one short hashrate
    window — so stress is always built on real work, not a fake load.
    """
    deadline = time.monotonic() + max(0.1, duration_s)
    samples = []
    while time.monotonic() < deadline or len(samples) < min_samples:
        t0 = time.monotonic() - (deadline - max(0.1, duration_s))
        rate = measure_fn()
        samples.append({"time_s": round(t0, 6), "rate": float(rate)})
    first = samples[0]["rate"]
    final = samples[-1]["rate"]
    degradation = ((first - final) / first * 100.0) if first > 0 else 0.0
    return {
        "duration_s": duration_s,
        "n_samples": len(samples),
        "samples": samples,
        "rate_initial": first,
        "rate_final": final,
        "degradation_pct": degradation,
    }
