# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Multi-route scheduling: several routes, one itinerary, disjoint nonce ranges.

HYBA Mine can run more than one local route at the same time (for example the
Chronus iGPU in Mode A on the CPU performance cores and the Metal route on the
Apple GPU of the same chip). Every route pulls its units from one
``WorkScheduler``:

* one ``ItineraryCursor`` per schedule (job, and version mask when the pool
  granted version rolling) decides the order; each route asks it for a unit of
  its own size (``RouteSizer``), and the cursor only moves forward;
* ranges the hashrate ceiling held back (a shortened unit's remainder, or a
  unit that had to wait) go to one shared queue and are handed out before the
  cursor moves on;
* ``InFlightRegistry`` checks every unit before it is dispatched: no two units
  of the same header (job, rolled version, extranonce2) may share a plan
  position, whether in flight or already issued for that job. A violation is a
  ``SchedulerInvariantError``; the runtime stops every route on it.

When the version mask changes mid-job the cursor restarts in the new version
space; ranges of headers already issued under the old mask are skipped, never
handed out twice.

Everything here is synchronous and must be called from the event-loop thread
only (checked: the first caller's thread is remembered).
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from hyba_mine.igpu import backend_of, route_compute_unit, route_label
from hyba_mine.plan import PythiaItinerary, RouteSizer, UnitSpec
from hyba_mine.work import CLIENT_VERSION_MASK, MiningJob, WorkUnit, make_unit, roll_version, version_space

SCHEDULER_KIND = "shared_itinerary"
INVARIANT = "disjoint (job, version, extranonce2, plan position range) across every route"
SLOT_STATES = ("starting", "running", "idle", "exhausted", "stopped", "faulted")


class SchedulerInvariantError(RuntimeError):
    """Two units of the same header would cover the same plan position."""

    def __init__(self, reason: str, unit: dict, conflict: Optional[dict] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.unit = unit
        self.conflict = conflict


def header_key(job_key: Any, version: int, en2_counter: int) -> tuple:
    return (job_key, version, en2_counter)


def unit_key(unit: WorkUnit) -> tuple:
    """The header a unit searches: (job key, full nVersion, extranonce2 counter)."""
    version = unit.version if unit.version is not None else unit.version_bits
    return header_key(unit.job.schedule_key if unit.job is not None else None, version, unit.en2_counter)


@dataclass(frozen=True)
class InFlight:
    slot_id: str
    route: str
    unit_id: str
    key: tuple
    start: int
    end: int

    def to_dict(self) -> dict:
        job_key, version, en2_counter = self.key
        return {"slot": self.slot_id, "route": self.route, "unit_id": self.unit_id,
                "job": list(job_key) if isinstance(job_key, tuple) else job_key,
                "version": f"{version:08x}", "en2_counter": en2_counter, "start": self.start, "end": self.end}


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


class InFlightRegistry:
    """Units in flight on every route, and the ranges issued for each header of the current job."""

    def __init__(self) -> None:
        self._by_unit: dict[str, InFlight] = {}
        self._issued: dict[tuple, list] = {}

    def __len__(self) -> int:
        return len(self._by_unit)

    def claim(self, slot_id: str, route: str, unit: WorkUnit) -> InFlight:
        key = unit_key(unit)
        entry = InFlight(slot_id, route, unit.unit_id, key, unit.start, unit.start + unit.count)
        if unit.unit_id in self._by_unit:
            raise SchedulerInvariantError("duplicate unit id", entry.to_dict(), self._by_unit[unit.unit_id].to_dict())
        for other in self._by_unit.values():
            if other.key == key and _overlaps(entry.start, entry.end, other.start, other.end):
                raise SchedulerInvariantError(f"overlaps an in-flight unit on route {other.route} ({other.slot_id})",
                                              entry.to_dict(), other.to_dict())
        for start, end in self._issued.get(key, ()):
            if _overlaps(entry.start, entry.end, start, end):
                conflict = {"route": None, "start": start, "end": end}
                raise SchedulerInvariantError("range already issued for this job", entry.to_dict(), conflict)
        self._by_unit[unit.unit_id] = entry
        self._merge(key, entry.start, entry.end)
        return entry

    def _merge(self, key: tuple, start: int, end: int) -> None:
        intervals = self._issued.setdefault(key, [])
        intervals.append([start, end])
        intervals.sort()
        merged = [intervals[0]]
        for a, b in intervals[1:]:
            if a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        self._issued[key] = merged

    def issued(self, key: tuple) -> list:
        return [tuple(interval) for interval in self._issued.get(key, ())]

    def release(self, unit_id: str) -> Optional[InFlight]:
        return self._by_unit.pop(unit_id, None)

    def retire_job(self, job_key: Any) -> None:
        """Forget the issued ranges of a job that will never be scheduled again."""
        for key in [k for k in self._issued if k[0] == job_key]:
            del self._issued[key]

    def clear_issued(self) -> None:
        self._issued.clear()

    def assert_disjoint(self) -> None:
        entries = list(self._by_unit.values())
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                if a.key == b.key and _overlaps(a.start, a.end, b.start, b.end):
                    raise SchedulerInvariantError(f"in-flight units on {a.route} and {b.route} overlap",
                                                  a.to_dict(), b.to_dict())

    def snapshot(self) -> list:
        return [entry.to_dict() for entry in self._by_unit.values()]


@dataclass
class RouteSlot:
    """One route of a run: its dispatcher, its unit size and what it has done."""

    slot_id: str
    dispatcher: Any
    route: str
    backend: str
    compute_unit: str
    expect_route: Optional[str]
    sizer: RouteSizer
    units: int = 0
    executed: int = 0
    device_ns: int = 0
    aborted_units: int = 0
    hits: int = 0
    inflight: Optional[WorkUnit] = None
    busy: bool = False
    state: str = "starting"
    stop_reason: Optional[str] = None
    aborted_executed: Optional[int] = None
    extra: dict = field(default_factory=dict)

    def backend_fields(self) -> dict:
        route = self.dispatcher.route
        fields = route.backend_fields() if hasattr(route, "backend_fields") else {
            "requested_backend": route.requested, "preference": "ours", "detected_backends": [],
            "executed_backend": self.backend, "fallback_reason": route.fallback_reason}
        if hasattr(self.dispatcher, "backend"):
            fields["requested_backend"] = self.dispatcher.backend
            fields["preference"] = self.dispatcher.prefer
        return fields

    def ledger_view(self) -> dict:
        return {"slot": self.slot_id, "route": self.route, "label": route_label(self.route),
                "backend": self.backend, "compute_unit": self.compute_unit, "dispatcher": self.dispatcher.describe()}

    def counters(self) -> dict:
        return {"slot": self.slot_id, "route": self.route, "backend": self.backend, "compute_unit": self.compute_unit,
                "units": self.units, "executed": self.executed, "device_ns": self.device_ns,
                "aborted_units": self.aborted_units, "hits": self.hits, "state": self.state}


def make_slot(slot_id: str, dispatcher: Any, itinerary: PythiaItinerary) -> RouteSlot:
    route = dispatcher.route.executed
    description = dispatcher.describe() if callable(getattr(dispatcher, "describe", None)) else {}
    local = isinstance(description, dict) and description.get("dispatcher") == "local"
    fleet = isinstance(description, dict) and description.get("dispatcher") == "fleet"
    if fleet:
        backend = getattr(dispatcher, "backend", backend_of(route))
        compute_unit = "remote_fleet"
    else:
        backend = backend_of(route)
        compute_unit = route_compute_unit(route)
    sizer = RouteSizer(itinerary.unit_size, itinerary.window_size, fixed=itinerary.override is not None)
    return RouteSlot(slot_id, dispatcher, route, backend, compute_unit, route if local else None, sizer)


class WorkScheduler:
    """Hands units of one shared itinerary to every route; see the module docstring."""

    def __init__(self, itinerary: PythiaItinerary, slots: list) -> None:
        self.itinerary = itinerary
        self.slots = slots
        self.registry = InFlightRegistry()
        self._schedule_key: Optional[tuple] = None
        self._job_key: Any = None
        self._job: Optional[MiningJob] = None
        self._mask = 0
        self._cursor = None
        self._pending: deque = deque()
        self._thread: Optional[int] = None

    def _check_thread(self) -> None:
        ident = threading.get_ident()
        if self._thread is None:
            self._thread = ident
        elif ident != self._thread:
            raise RuntimeError("the work scheduler must only be used from the event-loop thread")

    @property
    def override(self) -> bool:
        return self.itinerary.override is not None

    def reset(self) -> None:
        """Start over (a new pool session); nothing may be in flight."""
        self._check_thread()
        self._schedule_key = None
        self._job_key = None
        self._job = None
        self._cursor = None
        self._pending.clear()
        self.registry.clear_issued()

    def _select(self, job: MiningJob, mask: int) -> None:
        # A new version mask restarts the job's schedule in the new version space. An
        # explicit override list is consumed once per job; its version indices are checked
        # against the mask in force when each unit is taken (by the runtime).
        key = job.schedule_key if self.override else (job.schedule_key, mask)
        if key == self._schedule_key:
            return
        if job.schedule_key != self._job_key:
            if self._job_key is not None:
                self.registry.retire_job(self._job_key)
            self._job_key = job.schedule_key
        self._schedule_key = key
        self._job = job
        self._mask = mask
        space = version_space(CLIENT_VERSION_MASK if self.override else mask)
        self._cursor = self.itinerary.cursor(job.en2_limit, space)
        self._pending.clear()

    def _uncovered(self, job: MiningJob, mask: int, spec: UnitSpec) -> Optional[UnitSpec]:
        """The first part of ``spec`` not yet issued for its header; the rest goes back to the queue."""
        version, _bits = roll_version(job.base_version, mask, spec.version_index)
        issued = self.registry.issued(header_key(job.schedule_key, version, spec.en2_counter))
        if not issued:
            return spec
        begin, end = spec.start, spec.start + spec.count
        limit = end
        for a, b in issued:
            if b <= begin:
                continue
            if a <= begin:
                begin = b
                continue
            limit = min(limit, a)
            break
        if begin >= end:
            return None
        limit = min(limit, end)
        if limit < end:
            self._pending.appendleft(UnitSpec(spec.en2_counter, limit, end - limit, spec.version_index))
        return UnitSpec(spec.en2_counter, begin, limit - begin, spec.version_index)

    def _fit(self, spec: UnitSpec, size: int) -> UnitSpec:
        """The first ``size`` positions of ``spec``; the rest goes back to the front of the queue."""
        if size <= 0 or spec.count <= size:
            return spec
        self._pending.appendleft(UnitSpec(spec.en2_counter, spec.start + size, spec.count - size, spec.version_index))
        return UnitSpec(spec.en2_counter, spec.start, size, spec.version_index)

    def take(self, slot: RouteSlot, job: MiningJob, mask: int = 0) -> Optional[tuple]:
        """(next spec for ``slot``, whether it was held back earlier), or None when the schedule is done."""
        self._check_thread()
        self._select(job, mask)
        while True:
            if self._pending:
                spec, resumed = self._pending.popleft(), True
                if not self.override:
                    # A held-back range was sized by the route that produced it (possibly a
                    # much faster one); hand this route no more than its own unit size.
                    spec = self._fit(spec, slot.sizer.unit_size)
            else:
                spec, resumed = self._cursor.take(slot.sizer.unit_size), False
                if spec is None:
                    return None
            if self.override:
                return spec, resumed
            part = self._uncovered(job, mask, spec)
            if part is not None:
                return part, resumed or part != spec

    def put_back(self, spec: UnitSpec) -> None:
        """Return a range the ceiling held back; it is handed out before the cursor moves on."""
        self._check_thread()
        self._pending.appendleft(spec)

    def issue(self, slot: RouteSlot, job: MiningJob, spec: UnitSpec, difficulty, mask: int = 0) -> WorkUnit:
        """Build the unit for ``spec`` and claim it for ``slot`` (raises SchedulerInvariantError)."""
        self._check_thread()
        unit = make_unit(job, spec.en2_counter, spec.start, spec.count, difficulty, self.itinerary.window_bits,
                         version_mask=mask, version_index=spec.version_index)
        self.registry.claim(slot.slot_id, slot.route, unit)
        slot.inflight = unit
        return unit

    def complete(self, slot: RouteSlot, unit: WorkUnit) -> None:
        self._check_thread()
        self.registry.release(unit.unit_id)
        if slot.inflight is unit:
            slot.inflight = None

    def inflight_of_job(self, job_key: Any) -> list:
        return [slot for slot in self.slots if slot.inflight is not None and slot.inflight.job.key == job_key]

    def describe(self) -> dict:
        return {"kind": SCHEDULER_KIND, "routes": len(self.slots), "invariant": INVARIANT}
