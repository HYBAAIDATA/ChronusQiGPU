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
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional, Protocol

from chronus.execution.elevation import Route

from hyba_mine.work import Hit, WindowResult, WorkUnit


class DispatchError(RuntimeError):
    pass


class WindowDispatcher(Protocol):
    route: Route

    def describe(self) -> dict: ...

    async def run(self, unit: WorkUnit) -> WindowResult: ...

    def close(self) -> None: ...


class LocalIGPUDispatcher:
    """One local Chronus iGPU lane; one unit at a time."""

    def __init__(self, lane: Any, route: Route) -> None:
        self.lane = lane
        self.route = route
        self._lock = asyncio.Lock()

    def describe(self) -> dict:
        return {"dispatcher": "local", "route": self.route.to_dict(), "lane": self.lane.describe()}

    async def run(self, unit: WorkUnit) -> WindowResult:
        async with self._lock:
            return await asyncio.to_thread(self.lane.execute, unit)

    def close(self) -> None:
        self.lane.close()


class FleetDispatcher:
    """Adapter over ``chronus.fleet.FleetExecutor`` using the fleet's kernel-plugin contract."""

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

    async def run(self, unit: WorkUnit) -> WindowResult:
        from hyba_mine.fleet_kernel import decode_output

        fleet_unit = self.fleet_unit(unit)
        try:
            reply = await asyncio.to_thread(self.executor.submit, fleet_unit, self.timeout)
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
