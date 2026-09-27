"""Pure, deterministic Salamander control primitives.

The module contains the corrected state machines independently of MMIO so
they can be model-checked and unit-tested before being connected to silicon.
Actuators must return ``True`` only after a staged CSR commit is acknowledged.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Callable

LANES = 32
MIN_LANES = 24
FAULT_TAU_MS = 60_000
FAULT_TRIP = 3.0
REARM_HYST = 0.5
PROBATION_MS = 60_000
READMIT_PASSES = 3
FAILOVER_COOLDOWN_MS = 30_000
FAILOVER_DWELL_MS = 10_000
DWELL_TICKS = 400
TICK_MS = 50


@dataclass
class FaultBucket:
    level: list[float] = field(default_factory=lambda: [0.0] * LANES)
    last: list[int] = field(default_factory=lambda: [0] * LANES)
    previous: list[int] = field(default_factory=lambda: [0] * LANES)
    armed: list[bool] = field(default_factory=lambda: [True] * LANES)

    def update(self, cumulative_faults: list[int], now_ms: int) -> None:
        for lane in range(LANES):
            dt = max(now_ms - self.last[lane], 0)
            decay = math.exp(-dt / FAULT_TAU_MS) if self.last[lane] else 1.0
            delta = max(cumulative_faults[lane] - self.previous[lane], 0)
            self.level[lane] = self.level[lane] * decay + delta
            self.previous[lane] = cumulative_faults[lane]
            self.last[lane] = now_ms
            if not self.armed[lane] and self.level[lane] < REARM_HYST:
                self.armed[lane] = True


@dataclass
class NonceLedger:
    stride: int = LANES
    lane_wm: list[int] = field(default_factory=lambda: [0] * LANES)
    orphan: list[int] = field(default_factory=list)

    def retire(self, lane: int, active_count: int) -> None:
        heapq.heappush(self.orphan, self.lane_wm[lane])
        self.stride = max(active_count, 1)

    def readmit(self, lane: int, active_count: int) -> None:
        self.lane_wm[lane] = 0
        self.stride = max(active_count, 1)


@dataclass
class McLarenState:
    active: list[bool] = field(default_factory=lambda: [True] * LANES)
    quarantined_since: list[int] = field(default_factory=lambda: [0] * LANES)
    passes: list[int] = field(default_factory=lambda: [0] * LANES)


class McLarenController:
    """Fault-prune and probationary-readmit controller."""

    def __init__(self, state: McLarenState | None = None) -> None:
        self.state = state or McLarenState()
        self.degraded = False

    def step(
        self,
        bucket: FaultBucket,
        ledger: NonceLedger,
        now_ms: int,
        commit_lane_mask: Callable[[int], bool],
        self_test_lane: Callable[[int], bool],
    ) -> list[str]:
        actions: list[str] = []
        active_count = sum(self.state.active)
        for lane in range(LANES):
            if not self.state.active[lane] or not bucket.armed[lane]:
                continue
            if bucket.level[lane] < FAULT_TRIP:
                continue
            if active_count <= MIN_LANES:
                self.degraded = True
                actions.append("degraded_mode")
                break
            desired = sum((1 << i) for i, active in enumerate(self.state.active) if active) & ~(
                1 << lane
            )
            if commit_lane_mask(desired):
                self.state.active[lane] = False
                self.state.quarantined_since[lane] = now_ms
                self.state.passes[lane] = 0
                bucket.armed[lane] = False
                active_count -= 1
                ledger.retire(lane, active_count)
                actions.append(f"retire:{lane}")
                # One staged/acknowledged CSR transaction per supervisory tick.
                # The caller may invoke us again on the next tick.
                return actions
        for lane in range(LANES):
            if self.state.active[lane]:
                continue
            if now_ms - self.state.quarantined_since[lane] < PROBATION_MS:
                continue
            if self_test_lane(lane):
                self.state.passes[lane] += 1
            else:
                self.state.passes[lane] = 0
                self.state.quarantined_since[lane] = now_ms
                continue
            if self.state.passes[lane] >= READMIT_PASSES:
                desired = sum((1 << i) for i, active in enumerate(self.state.active) if active) | (
                    1 << lane
                )
                if commit_lane_mask(desired):
                    self.state.active[lane] = True
                    ledger.readmit(lane, sum(self.state.active))
                    actions.append(f"readmit:{lane}")
                    return actions
        return actions


@dataclass
class FailoverState:
    last_switch: int = -FAILOVER_COOLDOWN_MS
    secondary_since: int | None = None
    pending: bool = False

    def should_switch(self, drops: int, now_ms: int) -> bool:
        if drops <= 3 or self.pending or now_ms - self.last_switch < FAILOVER_COOLDOWN_MS:
            return False
        self.pending = True
        self.secondary_since = now_ms
        return True

    def mark_switch(self, now_ms: int) -> None:
        self.last_switch = now_ms
        self.secondary_since = now_ms
        self.pending = False

    def cancel_switch(self) -> None:
        self.pending = False
        self.secondary_since = None

    def primary_may_resume(self, now_ms: int) -> bool:
        """Require the secondary route to dwell before a future switch-back."""
        return (
            self.secondary_since is not None and now_ms - self.secondary_since >= FAILOVER_DWELL_MS
        )


@dataclass
class MichieState:
    """State for one-at-a-time propose/dwell/evaluate/revert experiments."""

    best_mask: int = 0
    best_score: float | None = None
    candidate: int | None = None
    cand_start: int = 0
    pending: bool = False


class MichieController:
    """Ack-gated directed mask trials with a fixed evaluation dwell."""

    def __init__(
        self,
        *,
        dwell_ms: int = DWELL_TICKS * TICK_MS,
        fault_penalty: float = 50.0,
    ) -> None:
        self.state = MichieState()
        self.dwell_ms = dwell_ms
        self.fault_penalty = fault_penalty

    def fitness(self, snapshot: dict[str, object]) -> float:
        hashes = snapshot.get("hashes_tested", [])
        faults = snapshot.get("faults", [])
        return float(sum(hashes)) - self.fault_penalty * float(sum(faults))

    @staticmethod
    def propose_mask(current_mask: int, faults: list[int]) -> int:
        hot = max(range(LANES), key=lambda lane: faults[lane]) if faults else 0
        shift = (hot + 1) % LANES
        mask = current_mask & 0xFFFFFFFF
        return ((mask << shift) | (mask >> (LANES - shift))) & 0xFFFFFFFF

    def step(
        self,
        *,
        current_mask: int,
        snapshot: dict[str, object],
        now_ms: int,
        commit_poly_mask: Callable[[int], bool],
    ) -> list[str]:
        actions: list[str] = []
        score = self.fitness(snapshot)
        if not self.state.pending:
            self.state.best_mask = current_mask & 0xFFFFFFFF
            self.state.best_score = score
            candidate = self.propose_mask(current_mask, list(snapshot.get("faults", [])))
            if candidate == self.state.best_mask:
                candidate = (candidate ^ 1) & 0xFFFFFFFF
            if commit_poly_mask(candidate):
                self.state.candidate = candidate
                self.state.cand_start = now_ms
                self.state.pending = True
                actions.append(f"trial:{candidate:#x}")
            return actions

        if now_ms - self.state.cand_start < self.dwell_ms:
            return actions

        candidate = self.state.candidate
        if candidate is None or self.state.best_score is None:
            self.state.pending = False
            return actions
        if score > self.state.best_score:
            self.state.best_score = score
            self.state.best_mask = candidate
            self.state.pending = False
            actions.append(f"accept:{candidate:#x}")
            return actions
        if commit_poly_mask(self.state.best_mask):
            actions.append(f"revert:{self.state.best_mask:#x}")
            self.state.pending = False
        return actions
