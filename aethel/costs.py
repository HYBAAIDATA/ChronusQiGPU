"""Aethel overhead accounting — measured CPU and memory cost of the substrate.

Every figure this module reports is **measured**, never simulated:

- CPU cost is ``time.process_time_ns()`` deltas around the real work —
  per-op nanoseconds attributable to this process only.  On platforms
  with a coarse process-time clock (Windows: ~15.6 ms ticks) a single
  fast op legitimately reports ``cpu_ns == 0``; the counter is
  cumulative, so aggregate cost over many ops still measures real CPU.
- Wall cost is ``time.perf_counter_ns()`` deltas — includes scheduling
  noise and I/O waits the CPU figure excludes.
- Payload bytes are recorded at the call sites that move real data.
- Memory is structural accounting: ``sys.getsizeof`` walked over the live
  containers.  It is an honest floor — Python's allocator overhead and the
  page tables backing an ``mmap`` region are not visible to ``getsizeof``.

The meter itself costs two clock reads (~50-100 ns) per instrumented op.
``process_time_ns`` is always-on: metering never changes the measured
behavior beyond that constant.
"""

from __future__ import annotations

import functools
import sys
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, Tuple


@dataclass
class OpCost:
    """Accumulated measured cost of one named operation."""

    calls: int = 0
    cpu_ns: int = 0
    wall_ns: int = 0
    payload_bytes: int = 0

    @property
    def cpu_ns_avg(self) -> float:
        return self.cpu_ns / self.calls if self.calls else 0.0

    @property
    def wall_ns_avg(self) -> float:
        return self.wall_ns / self.calls if self.calls else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "cpu_ns": self.cpu_ns,
            "cpu_ns_avg": self.cpu_ns_avg,
            "wall_ns": self.wall_ns,
            "wall_ns_avg": self.wall_ns_avg,
            "payload_bytes": self.payload_bytes,
        }


class OverheadMeter:
    """Per-object operation meter.  One meter per substrate component;

    shared components (a ``CassiniLedger`` shared by forked writers)
    naturally aggregate every writer's cost into the one ledger meter.
    """

    def __init__(self) -> None:
        self._ops: Dict[str, OpCost] = {}

    @contextmanager
    def measure(self, op: str, payload_bytes: int = 0) -> Iterator[None]:
        """Record CPU + wall time around the wrapped section."""
        t_cpu = time.process_time_ns()
        t_wall = time.perf_counter_ns()
        try:
            yield
        finally:
            cost = self._ops.setdefault(op, OpCost())
            cost.calls += 1
            cost.cpu_ns += time.process_time_ns() - t_cpu
            cost.wall_ns += time.perf_counter_ns() - t_wall
            cost.payload_bytes += payload_bytes

    def record_bytes(self, op: str, n: int) -> None:
        """Attribute ``n`` payload bytes to ``op`` without timing."""
        self._ops.setdefault(op, OpCost()).payload_bytes += n

    def merge(self, other: "OverheadMeter") -> None:
        """Fold another meter's accumulated costs into this one."""
        for name, cost in other._ops.items():
            mine = self._ops.setdefault(name, OpCost())
            mine.calls += cost.calls
            mine.cpu_ns += cost.cpu_ns
            mine.wall_ns += cost.wall_ns
            mine.payload_bytes += cost.payload_bytes

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Per-op measured totals (calls, cpu/wall ns, payload bytes)."""
        return {name: cost.to_dict() for name, cost in self._ops.items()}

    @property
    def total_cpu_ns(self) -> int:
        return sum(c.cpu_ns for c in self._ops.values())

    @property
    def total_wall_ns(self) -> int:
        return sum(c.wall_ns for c in self._ops.values())


def metered(op: str) -> Callable:
    """Decorator: time the method against ``self._costs``.

    Objects lacking a ``_costs`` attribute run uninstrumented — the
    decorator adds one attribute check and two clock reads per call.
    """

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            meter = getattr(self, "_costs", None)
            if meter is None:
                return fn(self, *args, **kwargs)
            with meter.measure(op):
                return fn(self, *args, **kwargs)

        return wrapper

    return deco


def container_bytes(obj: Any) -> int:
    """Structural memory floor for ``obj`` in bytes.

    ``sys.getsizeof`` on the container plus each element — dicts, lists,
    tuples and sets recurse one level per container.  This is an honest
    floor: it counts the object headers and contents Python exposes but
    not allocator slack, page tables, or interpreter bookkeeping.
    """
    if isinstance(obj, dict):
        return sys.getsizeof(obj) + sum(
            container_bytes(k) + container_bytes(v) for k, v in obj.items()
        )
    if isinstance(obj, (list, tuple, set, frozenset)):
        return sys.getsizeof(obj) + sum(container_bytes(x) for x in obj)
    return sys.getsizeof(obj)


def measure_alloc(fn: Callable[[], Any]) -> Tuple[Any, int]:
    """Run ``fn`` under ``tracemalloc`` and return ``(result, peak_bytes)``.

    ``peak_bytes`` is the measured peak allocation attributable to the
    call — the real allocation cost, not an estimate.  tracemalloc is
    enabled for the duration and restored afterwards.
    """
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        result = fn()
        _current, peak = tracemalloc.get_traced_memory()
        return result, peak
    finally:
        if not was_tracing:
            tracemalloc.stop()


__all__ = [
    "OpCost",
    "OverheadMeter",
    "container_bytes",
    "measure_alloc",
    "metered",
]
