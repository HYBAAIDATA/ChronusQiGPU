# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Where nonce windows execute: this Mac's Chronus iGPU lane, or the iGPU fleet.

The runtime hands each work unit to a ``WindowDispatcher`` and accepts the
result only after ``hyba_mine.work.check_result_integrity`` has checked it
(executed count, probe digest recomputed on the host, every hit on the plan).

* ``LocalIGPUDispatcher`` runs units on the lane pre-flight selected (the
  Chronus iGPU or Metal, by ``--backend`` and ``--prefer``).
* ``FleetDispatcher`` runs units on ``chronus.fleet`` through its public API:
  ``FleetExecutor.submit(chronus.fleet.WorkUnit) -> FleetResult`` (output
  bytes plus an ML-DSA-65 receipt that the executor has already verified). The
  unit names HYBA Mine's kernel plugin, ``hyba_mine.fleet_kernel``
  (``CHRONUS_FLEET_KERNELS=hyba_mine.fleet_kernel`` on every fleet machine);
  the fleet holds no mining logic. The unit's route is the requested backend
  (``auto`` lets each fleet worker's selection decide, steered by
  ``--prefer``); a backend no fleet machine offers fails closed.

When a unit's job goes stale the runtime calls ``abort(unit_id, grace)``. The
local dispatcher signals the lane (``lane.abort``), waits up to ``grace`` for
it to stop and reports what happened as an ``AbortReport``; it will not start
the next unit until the aborted one has left the lane (``drain_timeout``,
then it fails closed). ``chronus.fleet`` has no cancel API, so the fleet
dispatcher can only discard the result of an aborted unit.

Multi-route: a run may hold several ``LocalIGPUDispatcher`` instances, one per
lane (for example Mode A on the CPU performance cores and Metal on the Apple
GPU), each with its own lock, running at the same time on executor threads.
The runtime's ``hyba_mine.schedule.WorkScheduler`` guarantees they never
receive overlapping units.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional, Protocol

from chronus.execution.elevation import Route

from hyba_mine.igpu import node_name
from hyba_mine.work import AbortReport, Hit, UnitAborted, WindowResult, WorkUnit

FLEET_NO_CANCEL = "chronus.fleet has no cancel API; the remote job runs to completion and its result is discarded"


class DispatchError(RuntimeError):
    pass


class WindowDispatcher(Protocol):
    route: Route

    def describe(self) -> dict: ...

    async def run(self, unit: WorkUnit) -> WindowResult: ...

    # Optional: the runtime looks it up with getattr, so dispatchers without it still work.
    async def abort(self, unit_id: str, grace: float) -> AbortReport: ...

    def close(self) -> None: ...


def _consume_exception(future: "asyncio.Future") -> None:
    # Retrieve the exception of a future nobody may await again (an aborted unit).
    if not future.cancelled():
        future.exception()


async def _settle(future: "asyncio.Future", grace: float) -> tuple[bool, int]:
    started = time.monotonic_ns()
    if not future.done():
        await asyncio.wait({future}, timeout=max(0.0, grace))
    return future.done(), time.monotonic_ns() - started


def abort_report_from(future: "asyncio.Future", unit_id: str, route: str, node: str, signalled: bool,
                 waited_ns: int, detail: Optional[dict] = None) -> AbortReport:
    extra = dict(detail or {})
    if not future.done():
        return AbortReport(unit_id, signalled, "still_running", None, None, None, route, node, waited_ns, extra)
    if future.cancelled():
        return AbortReport(unit_id, signalled, "cancelled", None, None, None, route, node, waited_ns, extra)
    error = future.exception()
    if isinstance(error, UnitAborted):
        return AbortReport(unit_id, signalled, "stopped_early", error.executed, error.device_ns, error.hits_found,
                           error.route, error.node, waited_ns, extra)
    if error is not None:
        extra["error"] = type(error).__name__
        return AbortReport(unit_id, signalled, "failed", None, None, None, route, node, waited_ns, extra)
    result = future.result()
    return AbortReport(unit_id, signalled, "completed_before_stop", result.executed, result.device_ns,
                       len(result.hits), result.executed_route, result.node, waited_ns, extra)


class LocalIGPUDispatcher:
    """One local Chronus iGPU lane; one unit at a time.

    The lane call keeps running in its thread when the awaiting task is
    cancelled, so the dispatcher remembers it and does not hand the lane a
    new unit until it has finished (at most ``drain_timeout`` seconds).
    """

    def __init__(self, lane: Any, route: Route, *, drain_timeout: float = 30.0) -> None:
        self.lane = lane
        self.route = route
        self.drain_timeout = drain_timeout
        self._lock = asyncio.Lock()
        self._inflight: Optional[asyncio.Future] = None
        self._inflight_unit: Optional[str] = None

    def describe(self) -> dict:
        lane = self.lane.describe()
        record = {"dispatcher": "local", "route": self.route.to_dict(), "lane": lane}
        if isinstance(lane, dict) and lane.get("compute_unit"):
            record["compute_unit"] = lane["compute_unit"]
        return record

    def _clear(self, future: "asyncio.Future") -> None:
        if self._inflight is future:
            self._inflight = None
            self._inflight_unit = None

    async def _drain(self) -> None:
        future = self._inflight
        if future is None:
            return
        if not future.done():
            await asyncio.wait({future}, timeout=self.drain_timeout)
            if not future.done():
                raise DispatchError(f"the lane did not stop unit {self._inflight_unit} within "
                                    f"{self.drain_timeout:g} s after it was aborted")
        self._clear(future)
        error = None if future.cancelled() else future.exception()
        if error is not None and not isinstance(error, UnitAborted):
            raise DispatchError(f"lane fault while stopping an aborted unit: {type(error).__name__}: {error}") from error

    async def run(self, unit: WorkUnit) -> WindowResult:
        async with self._lock:
            await self._drain()
            future = asyncio.get_running_loop().run_in_executor(None, self.lane.execute, unit)
            future.add_done_callback(_consume_exception)
            self._inflight, self._inflight_unit = future, unit.unit_id
            try:
                return await asyncio.shield(future)
            finally:
                if future.done():
                    self._clear(future)

    async def abort(self, unit_id: str, grace: float) -> AbortReport:
        route = getattr(self.lane, "route", self.route.executed)
        future = self._inflight
        if future is None or self._inflight_unit != unit_id:
            return AbortReport(unit_id, False, "not_running", None, None, None, route, node_name(), 0)
        stop = getattr(self.lane, "abort", None)
        signalled = bool(stop(unit_id)) if callable(stop) else False
        done, waited_ns = await _settle(future, grace)
        if done:
            self._clear(future)
        return abort_report_from(future, unit_id, route, node_name(), signalled, waited_ns)

    def close(self) -> None:
        self.lane.close()


def _run_on_daemon_thread(fn, *args) -> "asyncio.Future":
    """Run ``fn(*args)`` on a daemon thread, so an abandoned call never holds up shutdown."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def deliver(ok: bool, value: Any) -> None:
        if future.done():
            return
        if ok:
            future.set_result(value)
        else:
            future.set_exception(value)

    def target() -> None:
        try:
            value, ok = fn(*args), True
        except Exception as exc:  # delivered to the awaiting coroutine
            value, ok = exc, False
        try:
            loop.call_soon_threadsafe(deliver, ok, value)
        except RuntimeError:
            pass  # the event loop has closed; nobody is waiting for this result

    future.add_done_callback(_consume_exception)
    threading.Thread(target=target, name="hyba-mine-fleet-unit", daemon=True).start()
    return future


class FleetDispatcher:
    """Adapter over ``chronus.fleet.FleetExecutor`` using the fleet's kernel-plugin contract.

    An aborted unit cannot be stopped on the fleet; its result is discarded.
    At most ``MAX_ABANDONED`` such units may still be running before the next
    unit waits for one of them (up to ``timeout``) or is refused.
    """

    MAX_ABANDONED = 2

    def __init__(self, executor: Any, route: Route, *, backend: str = "auto", prefer: str = "ours",
                 virtual_units: int = 800, timeout: float = 600.0) -> None:
        if not callable(getattr(executor, "submit", None)):
            raise DispatchError("fleet executor has no submit(work_unit) method")
        self.executor = executor
        self.route = route
        self.backend = "igpu" if backend == "mode_a" else backend
        self.prefer = prefer
        self.virtual_units = virtual_units
        self.timeout = timeout
        self._inflight: Optional[asyncio.Future] = None
        self._inflight_unit: Optional[str] = None
        self._abandoned: list = []

    def describe(self) -> dict:
        return {"dispatcher": "fleet", "route": self.route.to_dict(), "executor": type(self.executor).__name__,
                "kernel": "hyba_mine.nonce_window", "requested_backend": self.backend, "preference": self.prefer}

    def fleet_unit(self, unit: WorkUnit) -> Any:
        from chronus.fleet.workunit import WorkUnit as FleetWorkUnit

        from hyba_mine.fleet_kernel import KERNEL_NAME, KERNEL_VERSION, unit_params

        return FleetWorkUnit(
            kernel=KERNEL_NAME,
            payload=unit.header_prefix,
            params=unit_params(unit),
            route=self.backend,
            virtual_units=self.virtual_units,
            kernel_version=KERNEL_VERSION,
            label=f"hyba-mine {unit.unit_id}",
            prefer=self.prefer if self.backend == "auto" else None,
        )

    def _clear(self, future: "asyncio.Future") -> None:
        if self._inflight is future:
            self._inflight = None
            self._inflight_unit = None

    async def run(self, unit: WorkUnit) -> WindowResult:
        fleet_unit = self.fleet_unit(unit)
        self._abandoned = [f for f in self._abandoned if not f.done()]
        if len(self._abandoned) >= self.MAX_ABANDONED:
            await asyncio.wait({self._abandoned[0]}, timeout=self.timeout)
            self._abandoned = [f for f in self._abandoned if not f.done()]
            if len(self._abandoned) >= self.MAX_ABANDONED:
                raise DispatchError("too many abandoned fleet units are still running")
        future = _run_on_daemon_thread(self._submit_and_decode, unit, fleet_unit)
        self._inflight, self._inflight_unit = future, unit.unit_id
        try:
            result = await asyncio.shield(future)
        finally:
            if future.done():
                self._clear(future)
        if future in self._abandoned:
            # Aborted and abandoned: its result is never handed to the runtime.
            raise asyncio.CancelledError()
        return result

    async def abort(self, unit_id: str, grace: float) -> AbortReport:
        route, node = f"fleet:{self.backend}", "fleet"
        detail = {"device_stop_reason": FLEET_NO_CANCEL}
        future = self._inflight
        if future is None or self._inflight_unit != unit_id:
            return AbortReport(unit_id, False, "not_running", None, None, None, route, node, 0, detail)
        done, waited_ns = await _settle(future, grace)
        self._clear(future)
        if not done:
            self._abandoned.append(future)
        return abort_report_from(future, unit_id, route, node, False, waited_ns, detail)

    def _submit_and_decode(self, unit: WorkUnit, fleet_unit: Any) -> WindowResult:
        from hyba_mine.fleet_kernel import decode_output

        try:
            reply = self.executor.submit(fleet_unit, self.timeout)
        except Exception as exc:
            raise DispatchError(f"fleet refused or failed the unit: {type(exc).__name__}: {exc}") from exc
        receipt = getattr(reply, "receipt", None)
        if not getattr(reply, "verified", False) or not isinstance(receipt, dict):
            raise DispatchError("fleet result has no verified receipt")
        if receipt.get("work_unit", {}).get("digest") != fleet_unit.digest():
            raise DispatchError("fleet receipt belongs to another work unit")
        try:
            executed, hits, probe = decode_output(reply.output)
            tiles = receipt["routes"]["executed_tiles"]
            devices = receipt["devices"]
            backend = receipt.get("backend", {})
        except Exception as exc:
            raise DispatchError(f"fleet reply is malformed: {exc}") from exc
        return WindowResult(
            unit_id=unit.unit_id,
            executed=int(executed),
            device_ns=max(1, sum(int(d["exec_ns"]) for d in devices)),
            hits=tuple(Hit(int(offset), int(nonce)) for offset, nonce in hits),
            probe_words=tuple(int(word) for word in probe) if probe is not None else None,
            executed_route="fleet:" + "+".join(sorted(tiles)),
            node=",".join(sorted(str(d.get("label")) for d in devices)),
            detail={
                "timing": "fleet_device_time",
                "fleet_job": getattr(reply, "job_id", None),
                "receipt_id": receipt.get("receipt_id"),
                "backend": backend,
                "executed_backend": "+".join(sorted(backend.get("executed_backends") or tiles)),
                "tier": (receipt.get("tier") or {}).get("entitlement", {}).get("label"),
            },
        )

    def close(self) -> None:
        close = getattr(self.executor, "close", None)
        if callable(close):
            close()


def load_fleet_executor(coordinator_url: Optional[str] = None, token_file: Optional[str] = None,
                        tls_ca: Optional[str] = None) -> Optional[Any]:
    """A connected ``FleetExecutor`` if the fleet package is installed, else None."""
    try:
        from chronus.fleet.executor import FleetExecutor  # type: ignore[import-not-found]
    except ImportError:
        return None
    home = Path(os.environ.get("CHRONUS_FLEET_HOME", "~/.chronus/fleet")).expanduser()
    url = coordinator_url or os.environ.get("CHRONUS_FLEET_COORDINATOR") or "http://127.0.0.1:8740"
    token = token_file or (str(home / "token") if (home / "token").exists() else None)
    try:
        return FleetExecutor(url, token_file=token, tls_ca=tls_ca, name="hyba-mine")
    except Exception as exc:
        raise DispatchError(f"cannot reach the iGPU fleet at {url}: {type(exc).__name__}: {exc}") from exc
