# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Chronus iGPU lanes for HYBA Mine.

Chronus is HYBA's software-defined GPU. HYBA Mine detects the backends this
Mac offers and runs the canonical plan on the one the operator chooses
(``--backend``, ``--prefer ours|host``):

* ``igpu`` -> ``chronus_igpu_mode_a``: the Chronus iGPU in Mode A, our
  software-defined GPU, a first-class GPU route. ``--prefer ours`` (the
  default) selects it even when the Mac's own GPU is present.
* ``metal`` -> ``chronus_igpu_metal``: the plan bound to the host's Apple GPU
  through Metal (Mode B, see ``hyba_mine.metal``); ``--prefer host`` selects it
  when Metal is present and passes its known-answer tests.

Requested route, executed route and the reason the executed route differs from
the request are carried in ``chronus.execution.elevation.Route``;
``BackendRoute`` adds requested_backend, preference, detected_backends and
executed_backend.
"""

from __future__ import annotations

import concurrent.futures
import multiprocessing
import platform
import socket
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Optional

from chronus.execution.elevation import Route

from hyba_mine import _mode_a_kernel
from hyba_mine.work import Hit, UnitAborted, WindowResult, WorkUnit

ROUTE_METAL = "chronus_igpu_metal"
ROUTE_MODE_A = "chronus_igpu_mode_a"
#: Generic OpenCL route id; each GPU device gets its own route ``<this>_p<P>d<D>``.
ROUTE_OPENCL = "chronus_igpu_opencl"
ROUTE_LABELS = {
    ROUTE_METAL: "host GPU - Apple Metal (Mode B)",
    ROUTE_MODE_A: "Chronus iGPU - Mode A (software-defined GPU)",
    ROUTE_OPENCL: "host GPU - OpenCL (Mode B)",
}
BACKEND_IGPU = "igpu"
BACKEND_METAL = "metal"
BACKEND_OPENCL = "opencl"
ROUTE_BACKENDS = {ROUTE_MODE_A: BACKEND_IGPU, ROUTE_METAL: BACKEND_METAL, ROUTE_OPENCL: BACKEND_OPENCL}
REQUESTED_TO_ROUTE = {"metal": ROUTE_METAL, "mode_a": ROUTE_MODE_A, "igpu": ROUTE_MODE_A, "opencl": ROUTE_OPENCL}
#: Where each route physically executes (route names and labels are unchanged).
COMPUTE_CPU_PERFORMANCE_CORES = "cpu_performance_cores"
COMPUTE_APPLE_GPU = "apple_gpu"
COMPUTE_OPENCL_GPU = "opencl_gpu"
ROUTE_COMPUTE_UNITS = {ROUTE_MODE_A: COMPUTE_CPU_PERFORMANCE_CORES, ROUTE_METAL: COMPUTE_APPLE_GPU,
                       ROUTE_OPENCL: COMPUTE_OPENCL_GPU}
GPU_ROUTE_FAMILIES = (ROUTE_METAL, ROUTE_OPENCL)


def opencl_route(platform_index: int, device_index: int) -> str:
    return f"{ROUTE_OPENCL}_p{int(platform_index)}d{int(device_index)}"


def route_family(route: str) -> str:
    """The generic route of a per-device route (OpenCL); any other route unchanged."""
    if route == ROUTE_OPENCL or route.startswith(ROUTE_OPENCL + "_p"):
        return ROUTE_OPENCL
    return route


def route_label(route: str) -> str:
    if route_family(route) == ROUTE_OPENCL and route != ROUTE_OPENCL:
        return f"{ROUTE_LABELS[ROUTE_OPENCL]}, device {route[len(ROUTE_OPENCL) + 1:]}"
    return ROUTE_LABELS.get(route, route)


def route_compute_unit(route: str, default: str = "unknown") -> str:
    return ROUTE_COMPUTE_UNITS.get(route_family(route), default)


def is_gpu_route(route: str) -> bool:
    return route_family(route) in GPU_ROUTE_FAMILIES


def backend_of(route: str) -> str:
    """The --backend name of a lane route (fleet routes are already backend names)."""
    return ROUTE_BACKENDS.get(route_family(route), route)


@dataclass(frozen=True)
class BackendRoute(Route):
    """A Route plus the backend record: what was asked for, what was detected, what ran."""

    requested_backend: str = "auto"
    preference: str = "ours"
    detected_backends: tuple = ()
    executed_backend: str = ""

    def backend_fields(self) -> dict:
        return {
            "requested_backend": self.requested_backend,
            "preference": self.preference,
            "detected_backends": list(self.detected_backends),
            "executed_backend": self.executed_backend,
            "fallback_reason": self.fallback_reason,
        }

    def to_dict(self) -> dict:
        record = super().to_dict()
        record.update(self.backend_fields())
        return record


class LaneUnavailable(RuntimeError):
    """The lane's device or bindings are not present on this machine."""


class LaneFault(RuntimeError):
    """The lane is present but produced an untrustworthy result."""


def node_name() -> str:
    return socket.gethostname().split(".")[0] or "local"


def _performance_cores() -> int:
    if platform.system() == "Darwin":
        try:
            import subprocess

            done = subprocess.run(
                ["/usr/sbin/sysctl", "-n", "hw.perflevel0.physicalcpu"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if done.returncode == 0 and done.stdout.strip().isdigit():
                return int(done.stdout.strip())
        except (OSError, ValueError):
            pass
    # Elsewhere: logical CPUs this process may run on (affinity-aware), not the machine total.
    from hyba_mine.portable import available_cpus

    return available_cpus()[0]


class ModeALane:
    """Chronus iGPU Mode A: the plan executed by the software-defined GPU's worker processes.

    ``abort(unit_id)`` stops the unit in flight: every unit runs under a
    ticket held in shared memory, and the worker processes stop hashing when
    the ticket changes (checked on entry, every
    ``_mode_a_kernel.ABORT_CHECK_STRIDE`` candidates and at lane boundaries).
    Queued tasks are cancelled. The workers stay alive for the next unit. An
    abort that arrives before ``execute`` has registered its unit is remembered,
    and ``execute`` then refuses that unit (``UnitAborted`` with nothing run).

    ``always_pool`` runs every unit, even a small one, on the worker processes,
    never on a thread of this process: set when Mode A mines next to another
    route (Metal), so SHA-256d never competes with the Metal dispatch thread and
    the event loop for this process's interpreter lock. ``reserve_host_cores``
    leaves that many performance cores free for them when ``workers`` is not
    given.
    """

    route = ROUTE_MODE_A
    label = ROUTE_LABELS[ROUTE_MODE_A]

    def __init__(self, workers: Optional[int] = None, small_unit: int = 1 << 15, always_pool: bool = False,
                 reserve_host_cores: int = 0) -> None:
        if not isinstance(reserve_host_cores, int) or reserve_host_cores < 0:
            raise ValueError("reserved host cores must be a non-negative integer")
        if workers is None:
            workers = max(1, _performance_cores() - reserve_host_cores)
        else:
            reserve_host_cores = 0
        if not isinstance(workers, int) or workers < 1:
            raise ValueError("Mode A workers must be a positive integer")
        self.workers = workers
        self.small_unit = small_unit
        self.always_pool = bool(always_pool)
        self.reserve_host_cores = reserve_host_cores
        self._pool: Optional[ProcessPoolExecutor] = None
        self._ctx = multiprocessing.get_context("spawn")
        self._ticket = self._ctx.RawValue("Q", 0)
        self._state = threading.Lock()
        self._next_ticket = 1
        self._current: Optional[tuple[str, int]] = None
        self._futures: list = []
        # An abort that arrived before execute() registered its unit (the dispatcher
        # hands the unit to an executor thread that may not have started yet).
        self._pending_abort: Optional[str] = None

    def describe(self) -> dict:
        return {
            "route": self.route,
            "label": self.label,
            "workers": self.workers,
            "always_pool": self.always_pool,
            "reserved_host_cores": self.reserve_host_cores,
            "compute_unit": ROUTE_COMPUTE_UNITS[self.route],
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
        }

    def _executor(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(
                max_workers=self.workers, mp_context=self._ctx,
                initializer=_mode_a_kernel.install_abort_ticket, initargs=(self._ticket,),
            )
        return self._pool

    def _tasks(self, unit: WorkUnit) -> list[tuple[int, tuple]]:
        small = unit.count <= self.small_unit and not self.always_pool
        parts = 1 if (self.workers == 1 or small) else self.workers * 2
        lane = unit.plan.lane_size
        chunk = max(lane, ((unit.count + parts - 1) // parts + lane - 1) // lane * lane)
        tasks = []
        for rel in range(0, unit.count, chunk):
            size = min(chunk, unit.count - rel)
            probe = unit.probe_offset - rel if rel <= unit.probe_offset < rel + size else None
            args = (
                unit.header_prefix, unit.target, unit.start + rel, size, unit.plan.window_bits,
                unit.plan.offset, unit.plan.stride, unit.plan.lane_table, probe,
            )
            tasks.append((rel, args))
        return tasks

    def execute(self, unit: WorkUnit) -> WindowResult:
        tasks = self._tasks(unit)
        with self._state:
            pending, self._pending_abort = self._pending_abort, None
            if pending == unit.unit_id:
                # Aborted before it started: nothing runs, nothing is counted.
                raise UnitAborted(unit.unit_id, 0, 0, self.route, node_name())
            ticket = self._next_ticket
            self._next_ticket += 1
            self._ticket.value = ticket
            self._current = (unit.unit_id, ticket)

        def stop() -> bool:
            return self._ticket.value != ticket

        started = time.perf_counter_ns()
        try:
            if len(tasks) == 1 and not self.always_pool:
                outputs = [_mode_a_kernel.run_range(*tasks[0][1], should_stop=stop)]
            else:
                pool = self._executor()
                futures = [pool.submit(_mode_a_kernel.run_task_abortable, args, ticket) for _, args in tasks]
                with self._state:
                    self._futures = futures
                concurrent.futures.wait(futures)
                outputs = [(0, [], None) if f.cancelled() else f.result() for f in futures]
        finally:
            with self._state:
                self._current = None
                self._futures = []
        elapsed = time.perf_counter_ns() - started
        executed = 0
        hits: list[Hit] = []
        probe = None
        for (rel, _), (done, found, probe_words) in zip(tasks, outputs):
            executed += done
            hits.extend(Hit(rel + offset, nonce) for offset, nonce in found)
            if probe_words is not None:
                probe = probe_words
        if stop() and executed < unit.count:
            raise UnitAborted(unit.unit_id, executed, max(1, elapsed), self.route, node_name(), hits_found=len(hits))
        return WindowResult(
            unit_id=unit.unit_id,
            executed=executed,
            device_ns=max(1, elapsed),
            hits=tuple(sorted(hits, key=lambda h: h.offset)),
            probe_words=probe,
            executed_route=self.route,
            node=node_name(),
            detail={"timing": "host_wall_clock", "tasks": len(tasks), "workers": self.workers},
        )

    def abort(self, unit_id: str) -> bool:
        """Ask the workers to stop ``unit_id``.

        When that unit has not started here yet (``execute`` not yet registered it),
        the abort is remembered and ``execute`` refuses the unit; a remembered abort
        for any other unit is dropped when the next unit starts.
        """
        with self._state:
            if self._current is None or self._current[0] != unit_id:
                self._pending_abort = unit_id
                return True
            self._ticket.value = 0
            for future in self._futures:
                future.cancel()
            return True

    def close(self) -> None:
        # Running workers see the changed ticket and return at their next check.
        self._ticket.value = 0
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None
