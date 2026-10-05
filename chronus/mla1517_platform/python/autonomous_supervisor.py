"""Control-plane lifecycle supervisor with explicit mining authority boundaries.

This daemon supervises *process/control-plane* liveness. It may restart dead
worker processes through the canonical control plane, but it does not own
mining state, mining recovery, backend selection, share submission, or mining
parameter optimisation.

The canonical mining runtime owns those responsibilities:

* ``IntelligentPoolCoordinator`` / ``RecoveryGovernor`` own in-process mining
  recovery and execution-lane healing.
* ``ClosedLoopOptimizer`` owns measured mining-window optimisation and its
  retain/rollback lifecycle.
* ``MiningSession`` and the Stratum coordinator own share submission state.

CUOP remains available here as measured observation-only evidence. This module
must never write the mining nonce window or attach a second mining optimiser.
That keeps one authoritative closed-loop mining control plane while preserving
an outer supervisor that can revive a crashed worker process.
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

_AUTHORITY = {
    "scope": "control_plane_process_lifecycle",
    "worker_process_restarts": True,
    "mining_state_owner": "IntelligentPoolCoordinator",
    "mining_recovery_owner": "RecoveryGovernor/SelfHealingAgent",
    "mining_optimisation_owner": "ClosedLoopOptimizer",
    "share_submission_owner": "IntelligentPoolCoordinator/MiningSession",
    "mining_parameter_writes": False,
    "cuop_mode": "observation_only",
}


class AutonomousSupervisor:
    """Daemon supervising process liveness without competing with the miner.

    ``power_meter`` is the only power authority CUOP accepts: a callable that
    returns measured mean watts, or ``None`` when no reading exists. CUOP is
    reported as evidence only; it is not allowed to mutate mining parameters.
    """

    def __init__(
        self,
        interval_s: float = 60.0,
        power_meter: Optional[Callable[[], Optional[float]]] = None,
    ) -> None:
        self.interval_s = max(5.0, float(interval_s))
        self._power_meter = power_meter
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_result: dict[str, Any] = {}
        self._cycle_count = 0
        self._started_at: Optional[float] = None
        self._supervisor: Any = None
        # Compatibility attributes are intentionally always detached. Mining
        # optimisation belongs to the production coordinator.
        self._optimiser: Any = None
        self._measure_fn: Optional[Callable[[], Any]] = None
        self._cuop_status: dict[str, Any] = {
            "available": False,
            "evidence_class": "Unavailable",
            "reason": "not_measured",
        }

    def _build(self) -> None:
        """Lazy construction; never installs a second mining optimiser."""
        if self._supervisor is not None:
            return
        try:
            from Intelligence.autonomous_capabilities import (
                AutonomySupervisor,
                CassiniCycleLedger,
                CuopMeter,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Autonomous capabilities unavailable: %s", exc)
            self._supervisor = None
            return

        ledger = CassiniCycleLedger()
        supervisor = AutonomySupervisor(engine=None, ledger=ledger)

        def control_plane_probe() -> str:
            """Probe worker-process liveness only, not mining health."""
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
            """Revive worker processes through the control-plane lifecycle.

            This is intentionally not an in-process mining repair. Once the
            mining worker is alive, RecoveryGovernor/SelfHealingAgent regain
            sole authority over mining recovery.
            """
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

        meter = CuopMeter(usd_per_kwh=float(os.getenv("PYTHIA_CUOP_USD_KWH", "0.10")))

        def measure_cuop() -> Any:
            """Return measured CUOP or explicit unavailable evidence.

            ``PYTHIA_CUOP_POWER_W`` is configuration, not a measurement, so
            it never becomes runtime evidence.
            """
            try:
                import control_api as _ca

                power_raw = self._power_meter() if self._power_meter else None
                if power_raw is None:
                    raise RuntimeError(
                        "power_configured_not_measured"
                        if os.getenv("PYTHIA_CUOP_POWER_W")
                        else "power_telemetry_unavailable"
                    )
                power_w = float(power_raw)
                if not power_w > 0.0:
                    raise RuntimeError("power_telemetry_invalid")
                records = list(_ca._control_plane().records())
                measured_rates = [float(r.hashrate) for r in records if r.hashrate is not None]
                if not measured_rates:
                    raise RuntimeError("hashrate_telemetry_unavailable")
                reading = meter.measure(
                    useful_ops=sum(measured_rates) * self.interval_s,
                    mean_power_w=power_w,
                    window_s=self.interval_s,
                )
                self._cuop_status = {
                    "available": True,
                    "evidence_class": "Measured",
                    "reason": None,
                    "mode": "observation_only",
                    "reading": reading.to_dict(),
                }
                return reading
            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                self._cuop_status = {
                    "available": False,
                    "evidence_class": "Unavailable",
                    "reason": reason,
                    "mode": "observation_only",
                }
                logger.info("CUOP unavailable: %s", reason)
                return None

        # Measure for status/evidence, but never attach SelfOptimisingLoop or
        # write runtime_config.window. The mining coordinator's
        # ClosedLoopOptimizer is the sole nonce-window optimisation authority.
        measure_cuop()
        ledger.log(
            "supervision",
            {
                "trigger": "authority_boundary",
                "action": "mining_optimizer_not_attached",
                "reason": "mining_optimisation_owned_by_closed_loop_optimizer",
                "evidence_class": "Policy",
                "theorem_proven": False,
            },
        )
        self._supervisor = supervisor
        self._measure_fn = measure_cuop

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
                # Refresh CUOP as observation evidence each cycle. It is not
                # an optimisation input in this authority plane.
                if self._measure_fn is not None:
                    self._measure_fn()
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
                "authority": dict(_AUTHORITY),
                "cuop": dict(self._cuop_status),
                "supervisor": supervisor_status,
            }

    def trigger_cycle(self) -> dict[str, Any]:
        """Run one process-lifecycle supervision cycle synchronously."""
        self._build()
        if self._supervisor is None:
            return {"ok": False, "error": "supervisor not built"}
        if self._measure_fn is not None:
            self._measure_fn()
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
            return {
                "schema": "pythia.autonomous_supervisor/1",
                "running": False,
                "authority": dict(_AUTHORITY),
            }
        return _SUPERVISOR.status()


def trigger_cycle() -> dict[str, Any]:
    supervisor = ensure_started()
    return supervisor.trigger_cycle()
