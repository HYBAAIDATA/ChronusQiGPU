"""Shared measurement plumbing: timing, distributions, canonical JSON.

Every number that leaves this package is produced by executing real work and
timing it, or read from a real system surface. When a surface is absent the
field is ``None`` and the property name lands in ``unknown`` — nothing is
guessed or back-filled.
"""

from __future__ import annotations

import json
import platform
import statistics
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Iterable, List, Optional

from ..seam.types import Distribution


def now_ns() -> int:
    return time.perf_counter_ns()


def distribution_of(samples: Iterable[float]) -> Distribution:
    """Percentile summary of measured samples — never a scalar, never assumed."""
    values = sorted(float(s) for s in samples)
    if not values:
        return Distribution(mean=0.0, stddev=0.0, samples=0, p50=0.0, p95=0.0, p99=0.0)

    def pct(p: float) -> float:
        idx = min(len(values) - 1, max(0, int(round((p / 100.0) * (len(values) - 1)))))
        return values[idx]

    mean = statistics.fmean(values)
    return Distribution(
        mean=mean,
        stddev=statistics.pstdev(values) if len(values) > 1 else 0.0,
        samples=len(values),
        p50=pct(50),
        p95=pct(95),
        p99=pct(99),
    )


def unavailable(reason: str, **extra: Any) -> dict:
    """A stage that could not measure, stated instead of fabricated."""
    out = {"available": False, "reason": reason}
    out.update(extra)
    return out


def to_payload(obj: Any) -> Any:
    """Canonical JSON-safe form: dataclass -> dict, Distribution -> dict."""
    if isinstance(obj, Distribution):
        return obj.as_dict()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_payload(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_payload(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_payload(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(to_payload(obj), sort_keys=True, separators=(",", ":"), default=str)


def time_call(fn: Callable[[], Any]) -> float:
    """Wall-clock seconds around one real call."""
    start = now_ns()
    fn()
    return (now_ns() - start) / 1e9


def timed_calls(fn: Callable[[], Any], repeats: int) -> List[float]:
    """``repeats`` measured durations in nanoseconds, in call order."""
    durations = []
    for _ in range(max(1, int(repeats))):
        start = now_ns()
        fn()
        durations.append(now_ns() - start)
    return durations


def os_label() -> str:
    return f"{platform.system()} {platform.release()}"


def kernel_label() -> str:
    return platform.version()


def python_label() -> str:
    return platform.python_version()


def percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1))))]
