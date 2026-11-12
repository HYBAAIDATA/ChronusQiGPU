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

import multiprocessing
import os
import platform
import socket
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Optional

from chronus.execution.elevation import Route

from hyba_mine import _mode_a_kernel
from hyba_mine.work import Hit, WindowResult, WorkUnit

ROUTE_METAL = "chronus_igpu_metal"
ROUTE_MODE_A = "chronus_igpu_mode_a"
ROUTE_LABELS = {
    ROUTE_METAL: "host GPU - Apple Metal (Mode B)",
    ROUTE_MODE_A: "Chronus iGPU - Mode A (software-defined GPU)",
}
BACKEND_IGPU = "igpu"
BACKEND_METAL = "metal"
ROUTE_BACKENDS = {ROUTE_MODE_A: BACKEND_IGPU, ROUTE_METAL: BACKEND_METAL}
REQUESTED_TO_ROUTE = {"metal": ROUTE_METAL, "mode_a": ROUTE_MODE_A, "igpu": ROUTE_MODE_A}


def backend_of(route: str) -> str:
    """The --backend name of a lane route (fleet routes are already backend names)."""
    return ROUTE_BACKENDS.get(route, route)


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
    return os.cpu_count() or 1


class ModeALane:
    """Chronus iGPU Mode A: the plan executed by the software-defined GPU's worker processes."""

    route = ROUTE_MODE_A
    label = ROUTE_LABELS[ROUTE_MODE_A]

    def __init__(self, workers: Optional[int] = None, small_unit: int = 1 << 15) -> None:
        if workers is None:
            workers = max(1, _performance_cores())
        if not isinstance(workers, int) or workers < 1:
            raise ValueError("Mode A workers must be a positive integer")
        self.workers = workers
        self.small_unit = small_unit
        self._pool: Optional[ProcessPoolExecutor] = None

    def describe(self) -> dict:
        return {
            "route": self.route,
            "label": self.label,
            "workers": self.workers,
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
        }

    def _executor(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(
                max_workers=self.workers, mp_context=multiprocessing.get_context("spawn")
            )
        return self._pool

    def _tasks(self, unit: WorkUnit) -> list[tuple[int, tuple]]:
        parts = 1 if (self.workers == 1 or unit.count <= self.small_unit) else self.workers * 2
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
        started = time.perf_counter_ns()
        if len(tasks) == 1:
            outputs = [_mode_a_kernel.run_task(tasks[0][1])]
        else:
            outputs = list(self._executor().map(_mode_a_kernel.run_task, [args for _, args in tasks]))
        elapsed = time.perf_counter_ns() - started
        executed = 0
        hits: list[Hit] = []
        probe = None
        for (rel, _), (done, found, probe_words) in zip(tasks, outputs):
            executed += done
            hits.extend(Hit(rel + offset, nonce) for offset, nonce in found)
            if probe_words is not None:
                probe = probe_words
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

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None
