"""Where the mining time went, and why.

Decomposes measured wall time into the categories a mining operator acts on:

  useful_hashing   hashing of work that stayed valid
  stale_hashing    hashing of a window later abandoned as invalidated
  window_overhead  per-window cost outside hashing (plan, lease, launch, recheck)
  idle_no_plan     executor waited for a plan
  recovery         time with Salamander recovery active
  other            everything else between executions (submission, polling)

Hashing time is the device's kernel time when reported, otherwise the world
model's hash-rate estimate for that route; a window with neither is counted
as unattributed rather than guessed. Every figure derives from measured
records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .search_plan import CompletionState, ExecutionRecord
from .world_model import MiningWorldModel

CATEGORIES = (
    "useful_hashing",
    "stale_hashing",
    "window_overhead",
    "idle_no_plan",
    "recovery",
    "unattributed_execution",
)


@dataclass
class LossLedger:
    seconds: dict[str, float] = field(default_factory=lambda: {c: 0.0 for c in CATEGORIES})
    executions: int = 0
    hashes: int = 0
    stale_hashes: int = 0
    first_hash_latency_s: list[float] = field(default_factory=list)
    _started: float | None = None
    _last: float | None = None
    _pending_bind_at: float | None = None
    _recovery_since: float | None = None

    def start(self, now: float) -> None:
        if self._started is None:
            self._started = now
        self._last = now

    def observe_bind(self, now: float) -> None:
        self.start(now)
        self._pending_bind_at = now

    def observe_idle(self, seconds: float) -> None:
        if seconds > 0:
            self.seconds["idle_no_plan"] += seconds

    def observe_recovery(self, now: float, active: bool) -> None:
        self.start(now)
        if active and self._recovery_since is None:
            self._recovery_since = now
        elif not active and self._recovery_since is not None:
            self.seconds["recovery"] += max(0.0, now - self._recovery_since)
            self._recovery_since = None

    def observe_execution(
        self, record: ExecutionRecord, world: MiningWorldModel, *, started_at: float
    ) -> None:
        self.start(started_at)
        self.executions += 1
        self.hashes += max(0, record.hash_count)
        if self._pending_bind_at is not None and record.hash_count > 0:
            self.first_hash_latency_s.append(max(0.0, started_at - self._pending_bind_at))
            del self.first_hash_latency_s[:-256]
            self._pending_bind_at = None
        elapsed = max(0.0, record.elapsed_seconds)
        hashing = self._hashing_seconds(record, world)
        self._last = started_at + elapsed
        if hashing is None:
            self.seconds["unattributed_execution"] += elapsed
            return
        hashing = min(hashing, elapsed)
        stale = record.completion_state is CompletionState.INVALIDATED
        if stale:
            self.stale_hashes += max(0, record.hash_count)
        self.seconds["stale_hashing" if stale else "useful_hashing"] += hashing
        self.seconds["window_overhead"] += elapsed - hashing

    @staticmethod
    def _hashing_seconds(record: ExecutionRecord, world: MiningWorldModel) -> float | None:
        if record.kernel_ms > 0:
            return record.kernel_ms / 1e3
        route = world.route(record.executed_route or record.device_used or "unknown")
        estimate = route.estimate() if route is not None else None
        if estimate is None:
            return None
        return record.hash_count * estimate[1]

    def snapshot(self, now: float) -> dict[str, Any]:
        wall = 0.0 if self._started is None else max(0.0, now - self._started)
        seconds = dict(self.seconds)
        if self._recovery_since is not None:
            seconds["recovery"] += max(0.0, now - self._recovery_since)
        accounted = sum(seconds.values())
        seconds["other"] = max(0.0, wall - accounted)
        fractions = {k: (v / wall if wall > 0 else None) for k, v in seconds.items()}
        latencies = sorted(self.first_hash_latency_s)
        return {
            "schema": "pythia.loss/1",
            "wall_seconds": wall,
            "seconds": seconds,
            "fractions": fractions,
            "executions": self.executions,
            "hashes": self.hashes,
            "stale_hashes": self.stale_hashes,
            "time_to_first_hash_ms": (
                {
                    "p50": latencies[len(latencies) // 2] * 1e3,
                    "p90": latencies[(9 * len(latencies)) // 10] * 1e3,
                    "samples": len(latencies),
                }
                if latencies
                else None
            ),
        }
