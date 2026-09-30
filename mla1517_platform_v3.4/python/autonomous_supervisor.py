"""Consolidated self-healing / self-optimising supervisor.

Wires ``Intelligence.autonomous_capabilities`` into the control plane as a
continuous daemon. It unifies:

* Self-healing loop — probes registered subsystems and runs verified repairs.
* Self-optimising loop — measures CUOP and golden-step tunes the window size.
* Learner-drift supervision — retrains the validity learner when prediction
  error drifts above threshold (when a workflow is attached).
* Cassini ledger — every action is hash-chained and fingerprinted.

The supervisor is report-only by default. Repairs execute only when a
registered repair callable is provided and the post-repair probe confirms
HEALTHY. Optimiser parameter changes are applied, re-measured, and reverted
on regression.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("pythia.autonomous_supervisor")

_SUPERVISOR: Optional["AutonomousSupervisor"] = None
_SUPERVISOR_GUARD = threading.Lock()


class AutonomousSupervisor:
    """Daemon that runs the consolidated autonomy plane."""

    def __init__(self, interval_s: float = 60.0) -> None:
        self.interval_s = max(5.0, float(interval_s))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_result: dict[str, Any] = {}
        self._cycle_count = 0
        self._started_at: Optional[float] = None
        self._supervisor: Any = None
        self._optimiser: Any = None
        self._measure_fn: Optional[Callable[[], Any]] = None

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """Lazy import and construction so boot is not blocked."""
        if self._supervisor is not None:
            return
        try:
            from Intelligence.autonomous_capabilities import (
                AutonomySupervisor,
                CassiniCycleLedger,
                CuopLearner,
                CuopMeter,
                SelfOptimisingLoop,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Autonomous capabilities unavailable: %s", exc)
            self._supervisor = None
            return

        ledger = CassiniCycleLedger()
        supervisor = AutonomySupervisor(engine=None, ledger=ledger)

        # Register a subsystem probe for the local control plane.
        def control_plane_probe() -> str:
            try:
                import control_api as _ca

                control = _ca._control_plane()
                records = control.records()
                live = any(r.liveness for r in records)
                if not live and control.autostart:
                    return "subsystem_stall"
            except Exception as exc:
                logger.debug("control_plane_probe error: %s", exc)
                return "subsystem_stall"
            return "HEALTHY"

        def restart_workers() -> bool:
            try:
                import control_api as _ca

                control = _ca._control_plane()
                if not control.autostart:
                    control.set_autostart(True)
                control.ensure_workers()
                return True
            except Exception as exc:
                logger.warning("restart_workers repair failed: %s", exc)
                return False

        supervisor.heal_loop.register_subsystem(
            name="control_plane.workers",
            probe=control_plane_probe,
            repairs={"subsystem_stall": restart_workers},
        )

        # Self-optimising loop: tune the runtime config window size.
        meter = CuopMeter(usd_per_kwh=float(os.getenv("PYTHIA_CUOP_USD_KWH", "0.10")))

        def measure_cuop() -> Any:
            """Approximate CUOP from live telemetry counters."""
            try:
                import control_api as _ca

                control = _ca._control_plane()
                total_hashes = sum(
                    float(r.hashrate or 0.0) * self.interval_s for r in control.records()
                )
                # Approximate GPU power for an iGPU laptop; operator can override.
                power_w = float(os.getenv("PYTHIA_CUOP_POWER_W", "15.0"))
                return meter.measure(
                    useful_ops=max(1.0, total_hashes),
                    mean_power_w=power_w,
                    window_s=self.interval_s,
                )
            except Exception as exc:
                logger.debug("measure_cuop failed: %s", exc)
                return meter.measure(useful_ops=1.0, mean_power_w=1.0, window_s=1.0)

        def get_window() -> float:
            try:
                import runtime_config

                cfg = runtime_config.load()
                return float(cfg.get("window", 200000))
            except Exception:
                return 200000.0

        def set_window(value: float) -> None:
            try:
                import runtime_config

                cfg = runtime_config.load()
                window = int(value)
                bounds = cfg.get("bounds", {}).get("window", [1, 1 << 22])
                window = max(bounds[0], min(bounds[1], window))
                cfg["window"] = window
                runtime_config.save(cfg)
            except Exception as exc:
                logger.warning("set_window failed: %s", exc)

        learner = CuopLearner(
            name="nonce_window",
            getter=get_window,
            setter=set_window,
            lo=1000.0,
            hi=1_000_000.0,
            rel_step=0.25,
        )
        optimiser = SelfOptimisingLoop(meter=meter, learners=[learner], ledger=ledger)
        optimiser.measure_baseline(measure_cuop)
        supervisor.attach_optimiser(optimiser, measure_cuop)
        self._supervisor = supervisor
        self._optimiser = optimiser
        self._measure_fn = measure_cuop

    # ------------------------------------------------------------------
    # Daemon loop
    # ------------------------------------------------------------------
    def _loop(self) -> None:
        self._started_at = time.time()
        try:
            self._build()
        except Exception as exc:
            logger.error("Autonomous supervisor build failed: %s", exc)
            with self._lock:
                self._last_result = {"error": f"{type(exc).__name__}: {exc}"}
            return

        while not self._stop.is_set():
            try:
                if self._supervisor is not None:
                    result = self._supervisor.supervise_cycle()
                else:
                    result = {"error": "supervisor not built"}
                with self._lock:
                    self._last_result = result
                    self._cycle_count += 1
            except Exception as exc:
                logger.warning("Autonomous supervisor cycle failed: %s", exc)
                with self._lock:
                    self._last_result = {"error": f"{type(exc).__name__}: {exc}"}
            self._stop.wait(self.interval_s)

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, name="pythia-autonomous-supervisor", daemon=True
            )
            self._thread.start()
            return True

    def stop(self) -> bool:
        self._stop.set()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
        return False

    # ------------------------------------------------------------------
    # Status / control
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            supervisor_status = {}
            if self._supervisor is not None:
                try:
                    supervisor_status = self._supervisor.status()
                except Exception as exc:
                    supervisor_status = {"error": f"{type(exc).__name__}: {exc}"}
            return {
                "schema": "pythia.autonomous_supervisor/1",
                "running": running,
                "interval_s": self.interval_s,
                "cycle_count": self._cycle_count,
                "started_at": self._started_at,
                "last_result": self._last_result,
                "supervisor": supervisor_status,
            }

    def trigger_cycle(self) -> dict[str, Any]:
        """Run one cycle synchronously (for testing / manual intervention)."""
        self._build()
        if self._supervisor is None:
            return {"ok": False, "error": "supervisor not built"}
        result = self._supervisor.supervise_cycle()
        with self._lock:
            self._last_result = result
            self._cycle_count += 1
        return {"ok": True, "result": result}


def ensure_started(interval_s: Optional[float] = None) -> AutonomousSupervisor:
    """Idempotent accessor: create, configure, and start the supervisor."""
    global _SUPERVISOR
    with _SUPERVISOR_GUARD:
        if _SUPERVISOR is None:
            env_interval = os.getenv("PYTHIA_AUTONOMOUS_INTERVAL_S", "")
            if interval_s is None:
                try:
                    interval_s = float(env_interval)
                except ValueError:
                    interval_s = 60.0
            _SUPERVISOR = AutonomousSupervisor(interval_s=interval_s)
            _SUPERVISOR.start()
        return _SUPERVISOR


def stop() -> bool:
    with _SUPERVISOR_GUARD:
        if _SUPERVISOR is None:
            return False
        return _SUPERVISOR.stop()


def status() -> dict[str, Any]:
    with _SUPERVISOR_GUARD:
        if _SUPERVISOR is None:
            return {"schema": "pythia.autonomous_supervisor/1", "running": False}
        return _SUPERVISOR.status()


def trigger_cycle() -> dict[str, Any]:
    supervisor = ensure_started()
    return supervisor.trigger_cycle()
