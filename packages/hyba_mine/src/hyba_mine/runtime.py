# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""The HYBA Mine runtime: pool session, canonical plan, Chronus iGPU, ledger.

One loop, in order, for every work unit:

1. take the pool's current job (no job, no hashing);
2. take the next unit of the PYTHIA itinerary for that job and build its
   header prefix and Hendrix/golden-stride plan;
3. execute it on the Chronus iGPU lane through the dispatcher;
4. refuse the result unless it covers the whole unit, its probe digest equals
   the host's SHA-256d and every hit lies on the plan (otherwise the lane is
   faulty and mining stops);
5. recheck every hit on the host from the job fields (independent header path
   and SHA-256d against the exact share target) and drop hits whose job went
   stale;
6. submit, then record the pool's literal reply, or that none came.

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
from typing import Iterator, Optional

from hyba_mine import __version__
from hyba_mine.control import (
    block_pool,
    clear_control_request,
    read_control_request,
    update_state,
)
from hyba_mine.credentials import CredentialMissing, CredentialStore, require_login
from hyba_mine.dispatch import DispatchError, WindowDispatcher
from hyba_mine.igpu import LaneFault, backend_of, node_name
from hyba_mine.ledger import Ledger
from hyba_mine.paths import Layout
from hyba_mine.plan import DEFAULT_WINDOW_BITS, PLAN_VERSION, PythiaItinerary, UnitSpec
from hyba_mine.pools import get_pool
from hyba_mine.stratum import ConnectionLost, PoolSession, Submission, literal
from hyba_mine.work import HostRecheck, Hit, WindowResult, WorkUnit, check_result_integrity, make_unit

log = logging.getLogger("hyba_mine.runtime")

EXIT_OK = 0
EXIT_PREFLIGHT = 2
EXIT_DEVICE_FAULT = 3
EXIT_LOGIN_REJECTED = 4
EXIT_CONFIG = 5


class DeviceFault(RuntimeError):
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
        dispatcher: WindowDispatcher,
        pool_id: str,
        options: Optional[RuntimeOptions] = None,
    ) -> None:
        self.layout = layout
        self.ledger = ledger
        self.store = store
        self.dispatcher = dispatcher
        self.profile = get_pool(pool_id)
        self.options = options or RuntimeOptions()
        self.itinerary = self.options.itinerary or PythiaItinerary(
            window_bits=self.options.window_bits, windows_per_unit=self.options.windows_per_unit
        )
        self.recheck = HostRecheck()
        self.stats = WorkStats()
        self.session: Optional[PoolSession] = None
        self._session_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._stop_reason = "stopped by the operator"
        self._exit_code = EXIT_OK
        self._switch_to: Optional[tuple[str, str]] = None
        self._job_key: Optional[tuple] = None
        self._units: Optional[Iterator[UnitSpec]] = None
        self._reply_tasks: set[asyncio.Task] = set()

    # --------------------------------------------------------------- helpers
    def record(self, kind: str, data: dict) -> None:
        self.ledger.append(kind, data)

    def request_stop(self, reason: str = "stopped by the operator") -> None:
        if not self._stop.is_set():
            self._stop_reason = reason
            self._stop.set()
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
            **kwargs,
        )
        self.profile = profile
        self._job_key = None
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

    async def _apply_switch(self, request_id: str, pool_id: str) -> None:
        previous = self.profile.pool_id
        try:
            require_login(self.store, pool_id)
        except CredentialMissing as exc:
            self.record("pool_switch_refused", {"request_id": request_id, "pool": pool_id, "reason": str(exc)})
            return
        await self._close_session()
        await self._open_session(pool_id)
        update_state(self.layout, active_pool=pool_id)
        self.record("pool_switch_applied", {"request_id": request_id, "from": previous, "to": pool_id})

    # ------------------------------------------------------------ background
    async def _control_loop(self) -> None:
        while not self._stop.is_set():
            request = read_control_request(self.layout)
            if request is not None:
                clear_control_request(self.layout, request["request_id"])
                self.record("pool_switch_requested", {"request_id": request["request_id"], "pool": request["pool_id"], "source": "console"})
                self._switch_to = (request["request_id"], request["pool_id"])
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.options.control_interval)
            except asyncio.TimeoutError:
                pass

    def _backend_fields(self) -> dict:
        route = self.dispatcher.route
        fields = route.backend_fields() if hasattr(route, "backend_fields") else {
            "requested_backend": route.requested, "preference": "ours", "detected_backends": [],
            "executed_backend": backend_of(route.executed), "fallback_reason": route.fallback_reason}
        if hasattr(self.dispatcher, "backend"):
            fields["requested_backend"] = self.dispatcher.backend
            fields["preference"] = self.dispatcher.prefer
        return fields

    def _flush_stats(self) -> None:
        backend = self._backend_fields()
        for entry in self.stats.drain():
            route = entry["route"]
            executed = route[len("fleet:"):] if route.startswith("fleet:") else backend_of(route)
            self.record("work", {**entry, **backend, "executed_backend": executed})

    async def _stats_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.options.stats_interval)
            except asyncio.TimeoutError:
                self._flush_stats()

    # ---------------------------------------------------------------- mining
    def _next_spec(self, job) -> Optional[UnitSpec]:
        if job.key != self._job_key:
            self._job_key = job.key
            self._units = iter(self.itinerary.units(job.en2_limit))
        return next(self._units, None) if self._units is not None else None

    async def _mine(self) -> None:
        while not self._stop.is_set():
            if self._switch_to is not None:
                request_id, pool_id = self._switch_to
                self._switch_to = None
                await self._apply_switch(request_id, pool_id)
                continue
            session = self.session
            if session is None:
                return
            task = self._session_task
            if task is not None and task.done() and session.fatal is None and not self._stop.is_set():
                error = task.exception() if not task.cancelled() else None
                self._fail(EXIT_CONFIG, f"the pool session ended unexpectedly: {type(error).__name__ if error else 'cancelled'}")
                return
            if session.fatal is not None:
                block_pool(self.layout, self.profile.pool_id, "the pool rejected the login")
                self._fail(EXIT_LOGIN_REJECTED, f"{self.profile.name} rejected the login; run: hyba-mine login {self.profile.pool_id}")
                return
            job = await session.wait_for_job(timeout=1.0)
            if job is None:
                continue
            spec = self._next_spec(job)
            if spec is None:
                if self.options.stop_when_itinerary_ends:
                    self.request_stop("itinerary complete")
                    return
                session.changed.clear()
                try:
                    await asyncio.wait_for(session.changed.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue
            difficulty = session.difficulty if session.difficulty is not None else job.difficulty
            unit = make_unit(job, spec.en2_counter, spec.start, spec.count, difficulty, self.itinerary.window_bits)
            try:
                result = await self.dispatcher.run(unit)
            except (LaneFault, DispatchError) as exc:
                self._device_fault(unit, f"{type(exc).__name__}: {exc}")
                return
            problem = check_result_integrity(unit, result)
            if problem is not None:
                self._device_fault(unit, problem, result)
                return
            self.stats.add(result)
            self.itinerary.resize(result.device_ns / 1e9, self.options.target_unit_seconds)
            for hit in result.hits:
                try:
                    await self._handle_hit(unit, hit, session)
                except DeviceFault as exc:
                    self._device_fault(unit, str(exc), result)
                    return

    def _device_fault(self, unit: WorkUnit, reason: str, result: Optional[WindowResult] = None) -> None:
        self.record(
            "device_fault",
            {
                "unit_id": unit.unit_id,
                "route": result.executed_route if result else self.dispatcher.route.executed,
                "node": result.node if result else node_name(),
                "reason": reason,
            },
        )
        self._fail(EXIT_DEVICE_FAULT, f"Chronus iGPU lane fault: {reason}")

    async def _handle_hit(self, unit: WorkUnit, hit: Hit, session: PoolSession) -> None:
        job = unit.job
        base = {"unit_id": unit.unit_id, "pool": job.pool_id, "job_id": job.job_id, "en2": unit.en2.hex(), "nonce": f"{hit.nonce:08x}"}
        if self.session is not session or not session.is_valid(job):
            self.record("share_stale_dropped", {**base, "reason": "job no longer valid on the pool connection"})
            return
        outcome = self.recheck.check(job, unit.en2, hit.nonce, unit.difficulty)
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
            submission = await session.submit(job, unit.en2, hit.nonce)
        except ConnectionLost as exc:
            self.record("share_stale_dropped", {**base, "reason": f"not sent: {exc}"})
            return
        self.record("share_submitted", {**share, "request_id": submission.request_id, "endpoint": submission.endpoint.url})
        task = asyncio.create_task(self._await_reply(share["share_id"], submission))
        self._reply_tasks.add(task)
        task.add_done_callback(self._reply_tasks.discard)

    async def _await_reply(self, share_id: str, submission: Submission) -> None:
        started = time.monotonic_ns()
        try:
            reply = await asyncio.wait_for(asyncio.shield(submission.future), timeout=self.options.submit_timeout)
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
        self.record(
            "session_start",
            {
                "version": __version__,
                "node": node_name(),
                "pool": self.profile.pool_id,
                "requested_route": route.requested,
                "executed_route": route.executed,
                "fallback_reason": route.fallback_reason,
                **self._backend_fields(),
                "dispatcher": self.dispatcher.describe(),
                "plan": PLAN_VERSION,
                "window_bits": self.itinerary.window_bits,
                "tls_policy": self.options.tls_policy,
                "preflight": preflight,
            },
        )
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
            self.record("session_stop", {"reason": self._stop_reason, "exit_code": self._exit_code})
        return self._exit_code
