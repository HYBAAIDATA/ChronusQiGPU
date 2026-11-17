# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""The HYBA Mine runtime: pool session, canonical plan, Chronus iGPU, ledger.

One loop, in order, for every work unit:

1. take the pool's current job (no job, no hashing);
2. take the next unit of the PYTHIA itinerary for that job and build its
   header prefix (with the unit's BIP310 rolled version when the pool granted
   version rolling) and Hendrix/golden-stride plan;
3. execute it on the Chronus iGPU lane through the dispatcher, and abort it
   as soon as its job goes stale (clean_jobs, new extranonce, lost
   connection, pool switch, stop, or a ``mining.set_version_mask`` that no
   longer allows the unit's rolled bits): the dispatcher signals the lane, a
   ``unit_aborted_stale`` (or ``unit_aborted_shutdown``) record says what the
   device did, and the partial work is never counted as work or hashrate;
4. refuse the result unless it covers the whole unit, its probe digest equals
   the host's SHA-256d and every hit lies on the plan (otherwise the lane is
   faulty and mining stops);
5. drop hits whose job went stale or whose rolled version the pool's
   current mask would not rebuild, then recheck every hit on the host from the
   job fields (independent header path and SHA-256d against the exact share
   target, with the bits that will be submitted and the pool's own mask);
6. submit (6 params, the hashed version under the pool's mask, when version
   rolling was granted, else 5), then record the pool's literal reply, or that
   none came.

Version rolling only widens the search space; a unit still executes
``count`` candidates and is charged and measured as exactly that.

Before step 3 every unit is admitted by ``hyba_mine.throttle.CapGate`` against
chronus' process-wide hashrate ceiling (1 EH/s unless lowered by the published
limit file): a short grant shortens the unit (the rest is mined next), an
empty bucket makes the loop wait, and hashes a unit did not execute are
returned. The ceiling bounds work this process schedules; it is recorded as a
configured ceiling, never as a measured rate.

Several routes can mine at once (for example the Chronus iGPU in Mode A on
the CPU performance cores and Metal on the Apple GPU): ``_mine`` supervises one
loop per route (``RouteSlot``), and every loop takes its units from one shared
``hyba_mine.schedule.WorkScheduler``, so no two routes ever receive the same
(job, rolled version, extranonce2, position range). Every unit is checked
against the units in flight and the ranges already issued before it is
dispatched; a violation stops every route (``EXIT_SCHEDULER_FAULT``). A fault
on any route stops every route. One dispatcher is simply one route.

Measured work (executed candidates and device time per route) is written to
the ledger every few seconds; the console derives hashrate from those records
only.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from chronus.execution import hashrate_cap as _hc

from hyba_mine import __version__
from hyba_mine.control import (
    block_pool,
    block_for,
    clear_control_request,
    clear_stop_request,
    read_control_request,
    read_stop_request,
    update_state,
)
from hyba_mine.credentials import CredentialMissing, CredentialStore, require_login
from hyba_mine.dispatch import DispatchError, WindowDispatcher, abort_report_from
from hyba_mine.igpu import LaneFault, backend_of, node_name
from hyba_mine.ledger import Ledger
from hyba_mine.paths import Layout
from hyba_mine.plan import DEFAULT_WINDOW_BITS, LANE_SHIFT, PLAN_VERSION, PythiaItinerary, UnitSpec
from hyba_mine.schedule import RouteSlot, SchedulerInvariantError, WorkScheduler, make_slot
from hyba_mine.pools import get_pool
from hyba_mine.stratum import ConnectionLost, PoolSession, Submission, VersionMaskMismatch, literal
from hyba_mine.throttle import CapConfigError, CapGate
from hyba_mine.work import (
    AbortReport,
    HostRecheck,
    Hit,
    UnitAborted,
    WindowResult,
    WorkUnit,
    check_result_integrity,
    version_space,
)

log = logging.getLogger("hyba_mine.runtime")

EXIT_OK = 0
EXIT_PREFLIGHT = 2
EXIT_DEVICE_FAULT = 3
EXIT_LOGIN_REJECTED = 4
EXIT_CONFIG = 5
EXIT_SCHEDULER_FAULT = 6


class DeviceFault(RuntimeError):
    pass


class SchedulerFault(RuntimeError):
    pass


@dataclass
class RuntimeOptions:
    window_bits: int = DEFAULT_WINDOW_BITS
    windows_per_unit: int = 1
    tls_policy: str = "prefer"
    stats_interval: float = 10.0
    control_interval: float = 1.0
    submit_timeout: float = 60.0
    max_seconds: Optional[float] = None
    target_unit_seconds: float = 0.5
    itinerary: Optional[PythiaItinerary] = None
    stop_when_itinerary_ends: bool = False
    ssl_context: Optional[ssl.SSLContext] = None
    endpoints: dict = field(default_factory=dict)
    backoff: Optional[tuple] = None
    abort_grace: float = 2.0
    # Adopt the rate published in chronus' hashrate-cap limit file (only (0, 1] EH/s is accepted).
    adopt_published_cap: bool = True
    # Ask the pool for BIP310 version rolling (mining.configure); off sends 5-param submits only.
    version_rolling: bool = True
    # Route selection as pre-flight made it (multi-route runs): what was asked for, the
    # routes that are not running and why ({route, backend, reason, stage}), and the reason
    # the run has fewer routes than requested.
    requested_routes: Optional[tuple] = None
    unavailable_routes: tuple = ()
    degraded_reason: Optional[str] = None


class WorkStats:
    """Measured device work since the last ledger flush, per (node, route)."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.started_ns = time.monotonic_ns()
        self.by_lane: dict[tuple, list] = {}

    def add(self, result: WindowResult) -> None:
        entry = self.by_lane.setdefault((result.node, result.executed_route), [0, 0, 0, set()])
        entry[0] += result.executed
        entry[1] += result.device_ns
        entry[2] += 1
        timing = result.detail.get("timing") if isinstance(result.detail, dict) else None
        if timing:
            entry[3].add(timing)

    def drain(self) -> list[dict]:
        span = time.monotonic_ns() - self.started_ns
        records = [
            {
                "node": node,
                "route": route,
                "executed": executed,
                "device_ns": device_ns,
                "units": units,
                "timing": sorted(timing),
                "span_ns": span,
            }
            for (node, route), (executed, device_ns, units, timing) in self.by_lane.items()
            if executed
        ]
        self.reset()
        return records


class MinerRuntime:
    def __init__(
        self,
        layout: Layout,
        ledger: Ledger,
        store: CredentialStore,
        dispatcher: Union[WindowDispatcher, Sequence[WindowDispatcher]],
        pool_id: str,
        options: Optional[RuntimeOptions] = None,
    ) -> None:
        self.layout = layout
        self.ledger = ledger
        self.store = store
        self.dispatchers = list(dispatcher) if isinstance(dispatcher, (list, tuple)) else [dispatcher]
        if not self.dispatchers:
            raise ValueError("at least one dispatcher (route) is required")
        routes = [d.route.executed for d in self.dispatchers]
        if len(set(routes)) != len(routes):
            raise ValueError(f"each route may run once; got {', '.join(routes)}")
        self.profile = get_pool(pool_id)
        self.options = options or RuntimeOptions()
        self.itinerary = self.options.itinerary or PythiaItinerary(
            window_bits=self.options.window_bits, windows_per_unit=self.options.windows_per_unit
        )
        self.slots: list[RouteSlot] = [make_slot(f"r{i}", d, self.itinerary) for i, d in enumerate(self.dispatchers)]
        self.scheduler = WorkScheduler(self.itinerary, self.slots)
        # Set: routes may take work. Cleared while a pool switch is applied.
        self._gate = asyncio.Event()
        self._gate.set()
        self._slot_changed = asyncio.Event()
        self._worker_tasks: dict[str, asyncio.Task] = {}
        self.recheck = HostRecheck()
        self.stats = WorkStats()
        self.session: Optional[PoolSession] = None
        self._session_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        # Wakes the unit watcher for runtime events (stop, pool switch request).
        self._interrupt = asyncio.Event()
        self._stop_reason = "stopped by the operator"
        self._exit_code = EXIT_OK
        self._switch_to: Optional[tuple[str, str]] = None
        self._reply_tasks: set[asyncio.Task] = set()
        # The process-wide hashrate ceiling, shared by every route; the one place hashes are reserved.
        self.gate = CapGate()
        self._cap_seen: Optional[int] = None

    @property
    def dispatcher(self) -> WindowDispatcher:
        """The primary route's dispatcher (the only one in a single-route run)."""
        return self.dispatchers[0]

    # --------------------------------------------------------------- helpers
    def record(self, kind: str, data: dict) -> None:
        self.ledger.append(kind, data)

    def request_stop(self, reason: str = "stopped by the operator") -> None:
        if not self._stop.is_set():
            self._stop_reason = reason
            self._stop.set()
            self._interrupt.set()
            self._gate.set()
            self._slot_changed.set()
            if self.session is not None:
                self.session.stop()

    def _fail(self, code: int, reason: str) -> None:
        self._exit_code = code
        self.request_stop(reason)

    # --------------------------------------------------------------- session
    async def _open_session(self, pool_id: str) -> None:
        profile = get_pool(pool_id)
        login = require_login(self.store, profile.pool_id)
        kwargs = {}
        if self.options.backoff is not None:
            kwargs["backoff"] = self.options.backoff
        self.session = PoolSession(
            profile,
            login,
            record=self.record,
            tls_policy=self.options.tls_policy,
            ssl_context=self.options.ssl_context,
            endpoints=self.options.endpoints.get(profile.pool_id),
            version_rolling=self.options.version_rolling,
            **kwargs,
        )
        self.profile = profile
        self.scheduler.reset()
        self._session_task = asyncio.create_task(self.session.run(), name=f"pool-{profile.pool_id}")

    async def _close_session(self) -> None:
        if self.session is None:
            return
        self.session.stop()
        await self.session.disconnect()
        if self._session_task is not None:
            try:
                await asyncio.wait_for(self._session_task, timeout=15)
            except asyncio.TimeoutError:
                self._session_task.cancel()
        self.session = None
        self._session_task = None

    def _switch_refusal(self, pool_id: str) -> Optional[str]:
        """Why a switch to ``pool_id`` cannot be applied, or None when it can."""
        if block_for(self.layout, pool_id) is not None:
            return "pool is blocked by an earlier login rejection"
        try:
            require_login(self.store, pool_id)
        except CredentialMissing as exc:
            return str(exc)
        return None

    async def _apply_switch(self, request_id: str, pool_id: str) -> None:
        previous = self.profile.pool_id
        # Checked again here: a block or a removed login may have landed since the request.
        refusal = self._switch_refusal(pool_id)
        if refusal is not None:
            self.record("pool_switch_refused", {"request_id": request_id, "pool": pool_id, "reason": refusal})
            return
        await self._close_session()
        await self._open_session(pool_id)
        update_state(self.layout, active_pool=pool_id)
        self.record("pool_switch_applied", {"request_id": request_id, "from": previous, "to": pool_id})

    # ------------------------------------------------------------ background
    def _sync_cap(self) -> None:
        """Adopt a newly published limit and record any change of the ceiling."""
        if self.options.adopt_published_cap:
            try:
                _hc.apply_published_limit()
            except (ValueError, OSError) as exc:
                self.record("hashrate_cap_warning", {"reason": f"published limit not applied: {type(exc).__name__}: {exc}"})
        rate = self.gate.cap().cap_h_s
        if self._cap_seen is not None and rate != self._cap_seen:
            described = {k: v for k, v in self.gate.describe().items() if k != "cap_h_s"}
            self.record("hashrate_cap_changed", {"from_h_s": self._cap_seen, "to_h_s": rate, **described})
        self._cap_seen = rate

    async def _control_loop(self) -> None:
        while not self._stop.is_set():
            self._sync_cap()
            stop = read_stop_request(self.layout)
            if stop is not None:
                clear_stop_request(self.layout)
                self.record("stop_requested", {"request_id": stop["request_id"], "reason": stop.get("reason"),
                                               "source": "stop_request_file"})
                self.request_stop(f"stop requested ({stop.get('reason') or 'hyba-mine stop'})")
                break
            request = read_control_request(self.layout)
            if request is not None:
                clear_control_request(self.layout, request["request_id"])
                self.record("pool_switch_requested", {"request_id": request["request_id"], "pool": request["pool_id"], "source": "console"})
                # Refuse before any route is interrupted: a refused switch must not abort in-flight units.
                refusal = self._switch_refusal(request["pool_id"])
                if refusal is not None:
                    self.record("pool_switch_refused", {"request_id": request["request_id"],
                                                       "pool": request["pool_id"], "reason": refusal})
                else:
                    self._switch_to = (request["request_id"], request["pool_id"])
                    self._interrupt.set()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.options.control_interval)
            except asyncio.TimeoutError:
                pass

    def _backend_fields(self, slot: Optional[RouteSlot] = None) -> dict:
        return (slot or self.slots[0]).backend_fields()

    def _session_backend_fields(self) -> dict:
        """Backend fields for the whole session: every executing route's backend, not only the primary's.

        One route: exactly its fields. Several: ``executed_backend`` is "a+b" (like
        ``executed_route``), ``executed_backends`` lists them, and the requested and
        detected backends cover every route.
        """
        per_slot = [slot.backend_fields() for slot in self.slots]
        fields = dict(per_slot[0])

        def ordered(values) -> list:
            seen: list = []
            for value in values:
                if value not in seen:
                    seen.append(value)
            return seen

        executed = [f.get("executed_backend") for f in per_slot]
        fields["executed_backends"] = executed
        if len(per_slot) > 1:
            fields["executed_backend"] = "+".join(str(b) for b in executed)
            fields["requested_backend"] = "+".join(str(v) for v in ordered(f.get("requested_backend") for f in per_slot))
            fields["preference"] = "+".join(str(v) for v in ordered(f.get("preference") for f in per_slot))
            fields["detected_backends"] = ordered(b for f in per_slot for b in (f.get("detected_backends") or []))
        return fields

    def _slot_of_route(self, route: str) -> RouteSlot:
        # Fleet results report "fleet:<tiles>"; they belong to the (single) fleet slot.
        return next((slot for slot in self.slots if slot.route == route), self.slots[0])

    def _flush_stats(self) -> None:
        for entry in self.stats.drain():
            route = entry["route"]
            slot = self._slot_of_route(route)
            executed = route[len("fleet:"):] if route.startswith("fleet:") else backend_of(route)
            self.record("work", {**entry, **slot.backend_fields(), "executed_backend": executed,
                                 "slot": slot.slot_id, "compute_unit": slot.compute_unit})
        window = self.gate.drain()
        if window:
            self.record("hashrate_cap_window", window)

    async def _stats_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.options.stats_interval)
            except asyncio.TimeoutError:
                self._flush_stats()

    # ---------------------------------------------------------------- mining
    def _admit(self, spec: UnitSpec):
        """Reserve hashes for ``spec`` under the process ceiling: (spec to run, or None to wait; admission).

        A range the ceiling holds back goes back to the shared scheduler, so any route may take it next.
        """
        admission = self.gate.admit(spec.count, floor=1 << (self.itinerary.window_bits - LANE_SHIFT))
        if admission.positions == 0:
            self.scheduler.put_back(spec)
            return None, admission
        if admission.clamped:
            self.scheduler.put_back(UnitSpec(spec.en2_counter, spec.start + admission.positions,
                                             spec.count - admission.positions, spec.version_index))
            spec = UnitSpec(spec.en2_counter, spec.start, admission.positions, spec.version_index)
        return spec, admission

    def _set_state(self, slot: RouteSlot, state: str, *, busy: Optional[bool] = None) -> None:
        slot.state = state
        if busy is not None:
            slot.busy = busy
        self._slot_changed.set()

    def _session_failed(self, session: PoolSession) -> bool:
        """Stop the run when the pool session died or the pool rejected the login (True if so)."""
        if self._stop.is_set():
            return True
        task = self._session_task
        if task is not None and task.done() and session.fatal is None:
            error = task.exception() if not task.cancelled() else None
            self._fail(EXIT_CONFIG, f"the pool session ended unexpectedly: {type(error).__name__ if error else 'cancelled'}")
            return True
        if session.fatal is not None:
            block_pool(self.layout, self.profile.pool_id, "the pool rejected the login")
            self._fail(EXIT_LOGIN_REJECTED, f"{self.profile.name} rejected the login; run: hyba-mine login {self.profile.pool_id}")
            return True
        return False

    async def _wait_any(self, events: tuple, timeout: float) -> None:
        for event in events:
            event.clear()
        waiters = [asyncio.ensure_future(event.wait()) for event in events]
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiter in waiters:
                waiter.cancel()

    async def _routes_idle(self) -> None:
        """Wait until no route holds a unit (each has let go of its unit and handled its hits)."""
        while any(slot.busy for slot in self.slots) and not all(
                task.done() for task in self._worker_tasks.values()):
            self._slot_changed.clear()
            try:
                await asyncio.wait_for(self._slot_changed.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

    async def _mine(self) -> None:
        """Supervise one ``_route_loop`` per route: pool switches, session health, faults, the end."""
        for slot in self.slots:
            self.record("route_started", {**slot.ledger_view(), "unit_size": slot.sizer.unit_size,
                                          "scheduler": self.scheduler.describe()})
        self._worker_tasks = {slot.slot_id: asyncio.create_task(self._route_loop(slot), name=f"route-{slot.route}")
                              for slot in self.slots}
        tasks = self._worker_tasks
        reported: set = set()
        try:
            while not self._stop.is_set():
                if self._switch_to is not None:
                    self._gate.clear()
                    await self._routes_idle()
                    if self._stop.is_set():
                        break
                    request_id, pool_id = self._switch_to
                    self._switch_to = None
                    await self._apply_switch(request_id, pool_id)
                    if not self._stop.is_set():
                        self._interrupt.clear()
                    self._gate.set()
                    continue
                if self._interrupt.is_set() and not self._stop.is_set():
                    self._interrupt.clear()
                session = self.session
                if session is None:
                    self.request_stop("no pool session")
                    break
                if self._session_failed(session):
                    break
                for slot in self.slots:
                    task = tasks[slot.slot_id]
                    if slot.slot_id in reported or not task.done() or task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        reported.add(slot.slot_id)
                        self._set_state(slot, "faulted")
                        slot.stop_reason = f"{type(error).__name__}: {error}"[:300]
                        self.record("route_worker_failed", {"slot": slot.slot_id, "route": slot.route,
                                                            "error": slot.stop_reason})
                        self._fail(EXIT_DEVICE_FAULT, f"route {slot.route} failed: {slot.stop_reason}")
                if self._stop.is_set():
                    break
                if all(task.done() for task in tasks.values()):
                    if all(slot.state == "exhausted" for slot in self.slots):
                        self.request_stop("itinerary complete")
                    else:
                        self.request_stop("every route stopped")
                    break
                live = {task for task in tasks.values() if not task.done()}
                stop = asyncio.ensure_future(self._stop.wait())
                interrupt = asyncio.ensure_future(self._interrupt.wait())
                try:
                    await asyncio.wait({stop, interrupt, *live}, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    stop.cancel()
                    interrupt.cancel()
        finally:
            if not self._stop.is_set():
                self.request_stop(self._stop_reason)
            # The stop wakes every unit watcher, so in-flight units are aborted ("runtime_stopping").
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for slot, outcome in zip(self.slots, results):
                if isinstance(outcome, BaseException) and not isinstance(outcome, asyncio.CancelledError) \
                        and slot.slot_id not in reported:
                    slot.state = "faulted"
                    slot.stop_reason = f"{type(outcome).__name__}: {outcome}"[:300]
                    self.record("route_worker_failed", {"slot": slot.slot_id, "route": slot.route,
                                                        "error": slot.stop_reason})
                    if self._exit_code == EXIT_OK:
                        self._exit_code = EXIT_DEVICE_FAULT
                if slot.state not in ("exhausted", "faulted"):
                    slot.state = "stopped"
                self.record("route_stopped", {**slot.counters(), "reason": slot.stop_reason or self._stop_reason})

    async def _route_loop(self, slot: RouteSlot) -> None:
        """One route: take a unit from the shared scheduler, run it, check it, handle its hits."""
        try:
            await self._route_steps(slot)
        finally:
            slot.busy = False
            if slot.state in ("starting", "running", "idle"):
                slot.state = "stopped"
            self._slot_changed.set()

    async def _route_steps(self, slot: RouteSlot) -> None:
        while not self._stop.is_set():
            if self._switch_to is not None or not self._gate.is_set():
                self._gate.clear()
                self._set_state(slot, "idle", busy=False)
                await self._gate.wait()
                continue
            session = self.session
            if session is None:
                return
            if self._session_failed(session):
                return
            job = await session.wait_for_job(timeout=1.0)
            if job is None:
                if not self._session_failed(session):
                    await asyncio.sleep(0.01)  # never spin without yielding to the session task
                continue
            if self._stop.is_set() or self._switch_to is not None or self.session is not session:
                continue
            if not session.is_valid(job):
                continue
            mask = session.version_mask if session.version_rolling else 0
            try:
                taken = self.scheduler.take(slot, job, mask)
            except SchedulerInvariantError as exc:
                self._scheduler_fault(slot, exc)
                return
            if taken is None:
                if self.options.stop_when_itinerary_ends:
                    self._set_state(slot, "exhausted", busy=False)
                    if all(other.state in ("exhausted", "stopped", "faulted") for other in self.slots):
                        return
                    # Another route still holds a unit; a new job would reopen the itinerary.
                    await self._wait_any((session.changed, self._slot_changed), 0.2)
                    continue
                self._set_state(slot, "idle", busy=False)
                session.changed.clear()
                try:
                    await asyncio.wait_for(session.changed.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue
            spec, resumed = taken
            if spec.version_index >= version_space(mask):
                # Only an explicit override can get here (the schedule follows the mask).
                self.record("unit_skipped", {"en2_counter": spec.en2_counter, "start": spec.start, "count": spec.count,
                                             "version_index": spec.version_index, "version_mask": f"{mask:08x}",
                                             "slot": slot.slot_id, "route": slot.route,
                                             "reason": "version index is outside the pool's current version mask"})
                continue
            try:
                spec, admission = self._admit(spec)
            except CapConfigError as exc:
                self.record("hashrate_cap_warning", {"reason": str(exc), "route": slot.route})
                self._fail(EXIT_CONFIG, f"hashrate ceiling: {exc}")
                return
            if spec is None:
                await self.gate.pause(admission, self._stop)
                continue
            difficulty = session.difficulty if session.difficulty is not None else job.difficulty
            try:
                unit = self.scheduler.issue(slot, job, spec, difficulty, mask)
            except SchedulerInvariantError as exc:
                self.gate.settle(admission, 0)
                self._scheduler_fault(slot, exc)
                return
            self._set_state(slot, "running", busy=True)
            executed: Optional[int] = None
            try:
                result = await self._run_unit(unit, session, slot)
                executed = result.executed if result is not None else slot.aborted_executed
            except (LaneFault, DispatchError) as exc:
                self._device_fault(unit, f"{type(exc).__name__}: {exc}", slot=slot)
                return
            finally:
                self.gate.settle(admission, executed)
                self.scheduler.complete(slot, unit)
            if self._exit_code != EXIT_OK:
                # Another route faulted while this unit ran: nothing more from this run is used.
                return
            if result is None:
                self._set_state(slot, "idle", busy=False)
                continue
            if slot.expect_route is not None and result.executed_route != slot.expect_route:
                self._device_fault(unit, f"route mismatch: slot {slot.slot_id} runs {slot.route} but the lane "
                                         f"reported {result.executed_route}", result, slot)
                return
            problem = check_result_integrity(unit, result)
            if problem is not None:
                self._device_fault(unit, problem, result, slot)
                return
            self.stats.add(result)
            slot.units += 1
            slot.executed += result.executed
            slot.device_ns += result.device_ns
            if not (admission.clamped or resumed):
                # A unit shortened by the ceiling says nothing about the right unit size.
                slot.sizer.resize(result.device_ns / 1e9, self.options.target_unit_seconds)
            for hit in result.hits:
                slot.hits += 1
                try:
                    await self._handle_hit(unit, hit, session, slot)
                except DeviceFault as exc:
                    self._device_fault(unit, str(exc), result, slot)
                    return
            self._set_state(slot, "idle", busy=False)

    async def _watch_unit(self, session: PoolSession, unit: WorkUnit) -> str:
        """Why the unit in flight must stop: its job went stale (or its rolled bits left
        the pool's version mask), a pool switch, or a stop."""
        stale = asyncio.ensure_future(session.wait_stale(unit.job, unit.version, unit.version_bits))
        try:
            while True:
                interrupt = asyncio.ensure_future(self._interrupt.wait())
                try:
                    await asyncio.wait({stale, interrupt}, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    interrupt.cancel()
                if self._stop.is_set():
                    return "runtime_stopping"
                if stale.done():
                    return stale.result()
                if self._switch_to is not None:
                    return "pool_switch"
                self._interrupt.clear()
        finally:
            stale.cancel()

    async def _run_unit(self, unit: WorkUnit, session: PoolSession,
                        slot: Optional[RouteSlot] = None) -> Optional[WindowResult]:
        """Run one unit on its route, aborting it when its job goes stale; None when no whole result came back."""
        slot = slot or self.slots[0]
        started = time.monotonic_ns()
        slot.aborted_executed = None
        run_task = asyncio.create_task(slot.dispatcher.run(unit), name=f"unit-{unit.unit_id}")
        watch = asyncio.create_task(self._watch_unit(session, unit), name=f"watch-{unit.unit_id}")
        try:
            await asyncio.wait({run_task, watch}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            run_task.cancel()
            watch.cancel()
            await asyncio.gather(run_task, watch, return_exceptions=True)
            raise
        if run_task.done():
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)
            error = None if run_task.cancelled() else run_task.exception()
            if isinstance(error, UnitAborted):
                raise DispatchError("the lane stopped a unit that was not aborted") from error
            return run_task.result()
        reason = watch.result()
        return await self._abort_unit(unit, run_task, reason, started, time.monotonic_ns(), session, slot)

    async def _abort_unit(self, unit: WorkUnit, run_task: asyncio.Task, reason: str, started: int,
                          detected: int, session: PoolSession,
                          slot: Optional[RouteSlot] = None) -> Optional[WindowResult]:
        slot = slot or self.slots[0]
        slot.aborted_units += 1
        dispatcher = slot.dispatcher
        grace = self.options.abort_grace
        route, node = slot.route, node_name()
        report: Optional[AbortReport] = None
        abort = getattr(dispatcher, "abort", None)
        if callable(abort):
            try:
                report = await abort(unit.unit_id, grace)
            except Exception as exc:
                report = AbortReport(unit.unit_id, False, "failed", None, None, None, route, node,
                                     time.monotonic_ns() - detected, {"error": type(exc).__name__})
            if not run_task.done() and report.outcome != "still_running":
                # The route has let go of the unit; give the run a moment to hand back what it got.
                await asyncio.wait({run_task}, timeout=grace)
        if not run_task.done():
            run_task.cancel()
            await asyncio.wait({run_task}, timeout=grace)
        if report is None:
            report = abort_report_from(run_task, unit.unit_id, route, node, False, time.monotonic_ns() - detected)
        job = unit.job
        record = {
            "unit_id": unit.unit_id,
            "slot": slot.slot_id,
            "route": slot.route,
            "pool": job.pool_id,
            "job_id": job.job_id,
            "generation": job.generation,
            "epoch": job.epoch,
            "en2": unit.en2.hex(),
            "start": unit.start,
            "count": unit.count,
            "version_bits": f"{unit.version_bits:08x}",
            "version_mask": f"{unit.version_mask:08x}",
            "current_version_mask": f"{session.version_mask if session.version_rolling else 0:08x}",
            "current_pool_version_mask": f"{session.pool_version_mask if session.version_rolling else 0:08x}",
            "reason": reason,
            "replaced_by_job": session.current.job_id if session.current is not None and session.current is not job else None,
            "unit_elapsed_ms": (detected - started) // 1_000_000,
            "abort_latency_ms": (time.monotonic_ns() - detected) // 1_000_000,
            **report.ledger_fields(),
        }
        kind = "unit_aborted_shutdown" if reason == "runtime_stopping" else "unit_aborted_stale"
        if not run_task.done():
            self.record(kind, record)
            raise DispatchError("the dispatcher did not release an aborted unit")
        result: Optional[WindowResult] = None
        failure: Optional[BaseException] = None
        if not run_task.cancelled():
            failure = run_task.exception()
            if failure is None:
                result = run_task.result()
            elif isinstance(failure, UnitAborted):
                # The lane's own count of where it stopped: used only to return unexecuted
                # hashes to the ceiling, never as work or hashrate.
                slot.aborted_executed = failure.executed
                failure = None
        if result is not None:
            # A whole result arrived with the abort; it goes through the normal checks and,
            # if its job is stale, through the stale-hit drop.
            if check_result_integrity(unit, result) is not None:
                record["executed_basis"] = "whole_unit_failed_integrity_check"
        elif record.get("executed_basis") == "whole_unit_verified":
            record["executed_basis"] = "whole_unit_discarded_unverified"
        self.record(kind, record)
        if failure is not None:
            raise failure
        return result

    def _device_fault(self, unit: WorkUnit, reason: str, result: Optional[WindowResult] = None,
                      slot: Optional[RouteSlot] = None) -> None:
        slot = slot or self.slots[0]
        slot.state = "faulted"
        slot.stop_reason = reason
        self.record(
            "device_fault",
            {
                "unit_id": unit.unit_id,
                "route": result.executed_route if result else slot.route,
                "slot": slot.slot_id,
                "slot_route": slot.route,
                "node": result.node if result else node_name(),
                "reason": reason,
                "other_routes_stopped": [s.route for s in self.slots if s is not slot],
            },
        )
        self._fail(EXIT_DEVICE_FAULT, f"Chronus iGPU lane fault: {reason}")

    def _scheduler_fault(self, slot: RouteSlot, exc: SchedulerInvariantError) -> None:
        slot.state = "faulted"
        slot.stop_reason = f"scheduler invariant: {exc.reason}"
        self.record("scheduler_invariant_violated", {
            "slot": slot.slot_id, "route": slot.route, "reason": exc.reason, "unit": exc.unit,
            "conflict": exc.conflict, "inflight": self.scheduler.registry.snapshot(),
            "invariant": self.scheduler.describe()["invariant"],
        })
        self._fail(EXIT_SCHEDULER_FAULT, f"nonce scheduler invariant violated: {exc.reason}")

    async def _handle_hit(self, unit: WorkUnit, hit: Hit, session: PoolSession,
                          slot: Optional[RouteSlot] = None) -> None:
        job = unit.job
        base = {"unit_id": unit.unit_id, "route": slot.route if slot is not None else self.slots[0].route,
                "pool": job.pool_id, "job_id": job.job_id, "en2": unit.en2.hex(), "nonce": f"{hit.nonce:08x}",
                "version": f"{unit.version:08x}" if unit.version is not None else None,
                "version_bits": f"{unit.version_bits:08x}", "version_mask": f"{unit.version_mask:08x}"}
        if self.session is not session or not session.is_valid(job):
            self.record("share_stale_dropped", {**base, "reason": "job no longer valid on the pool connection"})
            return
        current_mask = session.version_mask if session.version_rolling else 0
        pool_mask = session.pool_version_mask if session.version_rolling else 0
        # Before the recheck: rechecking a hit under a mask that no longer rebuilds its
        # header would fail ABOVE_TARGET and be misread as a device fault.
        if not session.version_compatible(job, unit.version, unit.version_bits):
            self.record("share_stale_dropped", {**base, "current_mask": f"{current_mask:08x}",
                                                "pool_mask": f"{pool_mask:08x}",
                                                "reason": "rolled version bits no longer fit the pool's version mask (mining.set_version_mask)"})
            return
        # Recheck exactly what the pool will rebuild: the bits that will be submitted, under
        # the pool's own mask (which may be wider than the mask HYBA Mine rolls).
        wire_bits = session.submit_version_bits(unit.version) if session.version_rolling else 0
        outcome = self.recheck.check(job, unit.en2, hit.nonce, unit.difficulty,
                                     version_bits=wire_bits, version_mask=pool_mask)
        if not outcome.ok:
            if outcome.reason == "DUP":
                self.record("share_duplicate_dropped", base)
                return
            raise DeviceFault(f"host SHA-256d recheck rejected a device hit ({outcome.reason})")
        share = {
            **base,
            "share_id": f"{unit.unit_id}-{hit.offset}",
            "ntime": job.job.ntime,
            "hash": outcome.hash_hex,
            "share_target": f"{outcome.target:064x}",
            "difficulty": str(unit.difficulty),
            "block_candidate": outcome.block_candidate,
            "plan_position": unit.start + hit.offset,
            "host_recheck": "passed",
        }
        try:
            submission = await session.submit(job, unit.en2, hit.nonce, version=unit.version, version_bits=unit.version_bits,
                                              reply_expiry=max(120.0, 2 * self.options.submit_timeout))
        except (ConnectionLost, VersionMaskMismatch) as exc:
            self.record("share_stale_dropped", {**base, "reason": f"not sent: {exc}"})
            return
        self.record("share_submitted", {**share, "request_id": submission.request_id, "endpoint": submission.endpoint.url,
                                        "version_bits_submitted": submission.version_bits})
        task = asyncio.create_task(self._await_reply(share["share_id"], submission))
        self._reply_tasks.add(task)
        task.add_done_callback(self._reply_tasks.discard)

    async def _await_reply(self, share_id: str, submission: Submission) -> None:
        started = time.monotonic_ns()
        try:
            completed, _ = await asyncio.wait({submission.future}, timeout=self.options.submit_timeout)
            if not completed:
                raise asyncio.TimeoutError
            reply = submission.future.result()
        except asyncio.TimeoutError:
            self.record("share_unacknowledged", {"share_id": share_id, "reason": f"no pool reply within {self.options.submit_timeout:g} s"})

            def late(future: asyncio.Future) -> None:
                if future.cancelled() or future.exception() is not None:
                    return
                self._record_reply(share_id, future.result(), time.monotonic_ns() - started, late=True)

            submission.future.add_done_callback(late)
            return
        except ConnectionLost as exc:
            self.record("share_unacknowledged", {"share_id": share_id, "reason": f"connection lost before the pool replied ({exc})"})
            return
        self._record_reply(share_id, reply, time.monotonic_ns() - started, late=False)

    def _record_reply(self, share_id: str, reply: dict, latency_ns: int, late: bool) -> None:
        accepted = reply.get("result") is True and reply.get("error") is None
        self.record(
            "pool_response",
            {"share_id": share_id, "accepted": accepted, "reply": literal(reply), "latency_ms": latency_ns // 1_000_000, "late": late},
        )
        log.info("pool %s share %s", "ACCEPTED" if accepted else "REJECTED", share_id)

    # ------------------------------------------------------------------ main
    async def run(self, preflight: Optional[dict] = None) -> int:
        route = self.dispatcher.route
        options = self.options
        self._sync_cap()
        unavailable = [dict(entry) for entry in options.unavailable_routes]
        self.record(
            "session_start",
            {
                "version": __version__,
                "node": node_name(),
                "pool": self.profile.pool_id,
                "requested_route": route.requested,
                # One route: its name. Several: "a+b" (read executed_routes for the list).
                "executed_route": "+".join(slot.route for slot in self.slots),
                "executed_routes": [slot.route for slot in self.slots],
                "fallback_reason": route.fallback_reason or options.degraded_reason,
                **self._session_backend_fields(),
                "requested_routes": list(options.requested_routes) if options.requested_routes else None,
                "route_details": [slot.ledger_view() for slot in self.slots],
                "unavailable_routes": unavailable,
                "degraded": bool(unavailable),
                "degraded_reason": options.degraded_reason,
                "dispatcher": self.dispatcher.describe(),
                "dispatchers": [d.describe() for d in self.dispatchers],
                "scheduler": self.scheduler.describe(),
                "plan": PLAN_VERSION,
                "window_bits": self.itinerary.window_bits,
                "tls_policy": options.tls_policy,
                "hashrate_cap": self.gate.describe(),
                "preflight": preflight,
            },
        )
        for entry in unavailable:
            self.record("route_unavailable", {"stage": "detect", **entry})
        background: list[asyncio.Task] = []
        try:
            try:
                await self._open_session(self.profile.pool_id)
            except CredentialMissing as exc:
                self._fail(EXIT_CONFIG, str(exc))
                return self._exit_code
            background = [
                asyncio.create_task(self._control_loop(), name="control"),
                asyncio.create_task(self._stats_loop(), name="stats"),
            ]
            if self.options.max_seconds is not None:
                asyncio.get_running_loop().call_later(self.options.max_seconds, self.request_stop, "time limit reached")
            await self._mine()
        finally:
            self._stop.set()
            for task in background:
                task.cancel()
            await asyncio.gather(*background, return_exceptions=True)
            if self._reply_tasks:
                await asyncio.wait(set(self._reply_tasks), timeout=5)
            await self._close_session()
            if self._reply_tasks:
                await asyncio.wait(set(self._reply_tasks), timeout=2)
            self._flush_stats()
            self.record("session_stop", {"reason": self._stop_reason, "exit_code": self._exit_code,
                                         "hashrate_cap_h_s": self.gate.cap().cap_h_s})
        return self._exit_code
