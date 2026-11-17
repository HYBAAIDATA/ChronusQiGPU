# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Hashrate ceiling gate: the single point where HYBA Mine reserves hashes.

Every work unit the runtime dispatches, on any route (local lanes, Metal,
fleet units this process sends), is first admitted here against
``chronus.execution.hashrate_cap.process_cap()``: the process-wide integer
token bucket (1 EH/s unless lowered by the published limit file). The gate
looks the bucket up on every call and never keeps its own, so there is one
bucket per process and ``override_process_cap`` works in tests.

The ceiling limits the hashes this process *schedules*. It is not a
measurement: hashrate is still derived only from ``work`` records.

* ``admit`` reserves up to ``count`` plan positions (``hashes_per_position``
  hashes each). A short grant shortens the unit; a grant below ``floor``
  positions is returned and the caller waits ``wait_seconds``.
* ``settle`` returns the reserved hashes a unit did not execute, when the
  executed count is known. Unknown execution (lane fault, cancellation) keeps
  the charge: the conservative side of the ceiling.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Awaitable, Callable, Optional

from chronus.execution import hashrate_cap as _hc

SCOPE = "hashes scheduled by this hyba-mine process across all routes (local lanes and fleet units it dispatches)"
BASIS = "configured ceiling on hashes this process may schedule per second; not a measured rate"
WINDOW_BASIS = "hashes reserved and returned under the ceiling; not a device hashrate"
SOURCE = "chronus.execution.hashrate_cap.process_cap"
DEFAULT_MAX_WAIT_S = 0.25
MIN_WAIT_S = 0.001
_NS = 1_000_000_000


class CapConfigError(RuntimeError):
    """One plan position costs more hashes than the bucket can ever hold."""


@dataclass(frozen=True)
class Admission:
    requested: int  # plan positions asked for
    positions: int  # plan positions granted; 0 means wait
    hashes_per_position: int
    charged: int  # hashes taken from the bucket (positions * hashes_per_position)
    wait_seconds: float  # > 0 only when positions == 0
    cap_h_s: int  # ceiling at decision time

    @property
    def clamped(self) -> bool:
        return 0 < self.positions < self.requested


async def _wait_or_stop(seconds: float, stop: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


def _positive_int(name: str, value) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return value


def eh_s_text(cap_h_s: int) -> str:
    """Exact EH/s value of an integer H/s rate, e.g. ``1`` or ``0.000000000000004096``."""
    text = format(Decimal(cap_h_s) / Decimal(_hc.HASHES_PER_EH), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class CapGate:
    def __init__(
        self,
        *,
        cap_source: Optional[Callable[[], "_hc.HashrateCap"]] = None,
        sleeper: Optional[Callable[[float, asyncio.Event], Awaitable[None]]] = None,
        max_wait: float = DEFAULT_MAX_WAIT_S,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._cap_source = cap_source or (lambda: _hc.process_cap())
        self._sleeper = sleeper or _wait_or_stop
        self.max_wait = max_wait
        self._monotonic_ns = monotonic_ns
        self._reset()

    def _reset(self) -> None:
        self.granted = 0
        self.refunded = 0
        self.unsettled = 0
        self.waits = 0
        self.wait_ns = 0
        self.clamped_units = 0
        self.window_started_ns = self._monotonic_ns()

    def cap(self) -> "_hc.HashrateCap":
        return self._cap_source()

    def describe(self) -> dict:
        rate = self.cap().cap_h_s
        return {
            "cap_h_s": rate,
            "cap_eh_s": eh_s_text(rate),
            "ceiling_eh_s": _hc.HASHRATE_CAP_EH_S,
            "scope": SCOPE,
            "basis": BASIS,
            "source": SOURCE,
        }

    def admit(self, count: int, *, floor: int = 1, hashes_per_position: int = 1) -> Admission:
        """Reserve hashes for up to ``count`` positions now; never blocks."""
        count = _positive_int("count", count)
        floor = _positive_int("floor", floor)
        hpp = _positive_int("hashes_per_position", hashes_per_position)
        cap = self.cap()
        rate = cap.cap_h_s
        if hpp > rate:
            raise CapConfigError(f"one plan position costs {hpp} hashes, above the {rate} H/s ceiling")
        floor_positions = max(1, min(count, floor, rate // hpp))
        got = cap.allow(count * hpp)
        positions = got // hpp
        if positions < floor_positions:
            cap.refund(got)
            deficit = max(1, floor_positions * hpp - cap.available())
            wait_ns = max(cap.wait_ns(), (deficit * _NS + rate - 1) // rate)
            wait_s = min(self.max_wait, max(MIN_WAIT_S, wait_ns / _NS))
            self.waits += 1
            return Admission(count, 0, hpp, 0, wait_s, rate)
        charged = positions * hpp
        cap.refund(got - charged)
        self.granted += charged
        if positions < count:
            self.clamped_units += 1
        return Admission(count, positions, hpp, charged, 0.0, rate)

    async def pause(self, admission: Admission, stop: asyncio.Event) -> None:
        started = self._monotonic_ns()
        await self._sleeper(admission.wait_seconds, stop)
        self.wait_ns += max(0, self._monotonic_ns() - started)

    def settle(self, admission: Admission, executed_positions: Optional[int]) -> int:
        """Return the hashes of granted positions that did not run; 0 when execution is unknown."""
        if admission.positions == 0:
            return 0
        if executed_positions is None:
            self.unsettled += admission.charged
            return 0
        done = min(max(int(executed_positions), 0), admission.positions)
        refund = (admission.positions - done) * admission.hashes_per_position
        if refund:
            self.cap().refund(refund)
            self.refunded += refund
        return refund

    def drain(self) -> Optional[dict]:
        """Counters since the last drain, or None when the ceiling did not bind and nothing was refunded."""
        if not (self.waits or self.clamped_units or self.refunded or self.unsettled):
            self._reset()
            return None
        window = {
            "cap_h_s": self.cap().cap_h_s,
            "granted_hashes": self.granted,
            "refunded_hashes": self.refunded,
            "unsettled_hashes": self.unsettled,
            "throttle_waits": self.waits,
            "throttled_ns": self.wait_ns,
            "clamped_units": self.clamped_units,
            "span_ns": max(0, self._monotonic_ns() - self.window_started_ns),
            "scope": SCOPE,
            "basis": WINDOW_BASIS,
        }
        self._reset()
        return window
