"""Salamander — systems engineer for the one live miner.

Keeps the pool connection afloat. Does not mine.
Uses existing SalamanderEngine + SalamanderZeroTrustGovernor.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hyba.mining.salamander")


def _load_engine():
    try:
        from python_backend.salamander import SalamanderEngine

        return SalamanderEngine()
    except Exception as exc:
        logger.info("[SALAMANDER] Engine import skipped: %s", exc)
        return None


def _load_governor():
    try:
        from python_backend.hyba.salamander.governor import SalamanderZeroTrustGovernor

        gov = SalamanderZeroTrustGovernor(max_allowed_execution_sec=30.0)
        gov.register_worker("pool_primary")
        gov.register_worker("pool_failover")
        return gov
    except Exception as exc:
        logger.info("[SALAMANDER] Governor import skipped: %s", exc)
        return None


class SalamanderSystemsEngineer:
    """Checks pool connection, job freshness, and heals the live loop."""

    def __init__(self, stale_seconds: float = 120.0):
        self.engine = _load_engine()
        self.governor = _load_governor()
        self.stale_seconds = stale_seconds
        self.last_job_id: Optional[str] = None
        self.job_first_seen_at: Optional[float] = None
        # Stale-job recovery (post-audit fix): a pool socket can stay
        # TCP-CONNECTED while the job stream silently dies (half-open
        # connection / dead notify push). keep_afloat() previously only set
        # need_reconnect when status != CONNECTED, so a stalled job stream
        # paused hashing FOREVER -- the stale trip protected mining to death.
        # Now prolonged staleness requests a reconnect onto a fresh job
        # stream, throttled by a cooldown so a genuinely quiet pool cannot
        # be hammered with reconnect attempts every supervisor tick.
        self.stale_reconnect_cooldown_seconds: float = float(
            os.getenv("HYBA_STALE_RECONNECT_COOLDOWN_SECONDS", "30")
        )
        self._last_stale_reconnect_request_at: Optional[float] = None
        logger.info("[SALAMANDER] Systems engineer online | pool keep-alive + heal")

    def keep_afloat(self, stratum: Any) -> Dict[str, Any]:
        status = getattr(stratum, "status", "DISCONNECTED")
        job = getattr(stratum, "current_job", None) or {}
        job_id = job.get("job_id") if isinstance(job, dict) else None
        now = time.time()
        need_reconnect = status != "CONNECTED"
        need_failover = False
        stale = False
        age = 0.0

        if job_id != self.last_job_id:
            self.last_job_id = job_id
            self.job_first_seen_at = now if job_id else None
        if job_id and self.job_first_seen_at:
            age = now - self.job_first_seen_at
            stale = age > self.stale_seconds

        if need_reconnect and self.governor is not None:
            self.governor.trip_node("pool_primary", "POOL_DISCONNECTED")
            need_failover = True
        if stale and self.governor is not None:
            self.governor.trip_node("pool_primary", "JOB_STALE")
            logger.warning(
                "[SALAMANDER] Job %s unchanged for %.0fs — pool may be stalled",
                job_id,
                age,
            )
            # Stale-job recovery: the socket may look CONNECTED while the
            # notify stream is dead. Request a reconnect (cooldown-throttled)
            # so stale protection cannot permanently prevent mining.
            since_last = now - (self._last_stale_reconnect_request_at or 0.0)
            if since_last >= self.stale_reconnect_cooldown_seconds:
                need_reconnect = True
                self._last_stale_reconnect_request_at = now
                logger.warning(
                    "[SALAMANDER] Stale job stream on a live socket — requesting reconnect "
                    "(age=%.0fs, cooldown=%.0fs)",
                    age,
                    self.stale_reconnect_cooldown_seconds,
                )

        homeostasis = None
        if self.engine is not None:
            try:
                homeostasis = self.engine.check_homeostasis()
            except Exception as exc:
                logger.info("[SALAMANDER] Homeostasis skipped: %s", exc)

        # Autonomic IPC Failure Ingestion & Circuit Tripping
        autonomic_actions: List[Dict[str, Any]] = []
        telemetry_degraded = False
        try:
            from python_backend.hyba.salamander.salamander_failure_bus import SalamanderFailureBus

            bus = SalamanderFailureBus.get_instance()
            failures = bus.poll(max_items=10)
            for fail in failures:
                logger.error(
                    "[SALAMANDER AUTONOMICS] Intercepted failure: %s on %s",
                    fail.failure_type,
                    fail.worker_id,
                )
                # Sensor permission drops or physical telemetry anomalies lock billing fail-closed
                if any(
                    k in fail.failure_type
                    for k in (
                        "SENSOR_PERMISSION_DROP",
                        "INVALID_TELEMETRY",
                        "RAPL_OVERFLOW_ANOMALY",
                    )
                ):
                    try:
                        from python_backend.enterprise.outcome_billing import (
                            get_outcome_billing_engine,
                        )

                        get_outcome_billing_engine().lock_billing(fail.failure_type)
                        telemetry_degraded = True
                    except Exception as bill_err:
                        logger.debug("[SALAMANDER] Could not lock billing engine: %s", bill_err)

                if self.governor is not None:
                    self.governor.trip_node(fail.worker_id, fail.failure_type)
                action = self.autonomic_fallback(fail)
                autonomic_actions.append(action)
                need_failover = True
        except Exception as bus_exc:
            logger.debug("[SALAMANDER] Failure bus poll skipped: %s", bus_exc)

        report = {
            "need_reconnect": need_reconnect,
            "need_failover": need_failover,
            "connected": status == "CONNECTED",
            "has_job": bool(job_id),
            "job_id": job_id,
            "stale": stale,
            "age_seconds": age,
            "homeostasis": homeostasis,
            "engineer": "salamander",
            "autonomic_actions": autonomic_actions,
            "telemetry_degraded": telemetry_degraded,
        }
        if need_reconnect:
            logger.warning("[SALAMANDER] Pool down — requesting reconnect")
        return report

    def autonomic_fallback(self, event: Any) -> Dict[str, Any]:
        """Handles worker failure by isolating the worker, pivoting to CPU fallback lane, and logging to WORM ledger."""
        from python_backend.hyba.salamander.salamander_failure_bus import SalamanderFailureBus

        fallback_lane = "cpu_single_process"
        worm_entry = SalamanderFailureBus.get_instance().record_state_degradation(
            event=event,
            fallback_lane=fallback_lane,
        )
        logger.warning(
            "[SALAMANDER AUTONOMICS] Worker %s failed (%s). Autonomically shifted execution to lane %s.",
            event.worker_id,
            event.failure_type,
            fallback_lane,
        )
        return {
            "worker_id": event.worker_id,
            "failure_type": event.failure_type,
            "fallback_lane": fallback_lane,
            "worm_signature": worm_entry.get("signature"),
        }

    def heal(self, error_count: int) -> Dict[str, Any]:
        status = "HEALTHY" if error_count == 0 else "RECOVERING"
        if error_count == 0 and self.governor is not None:
            try:
                from python_backend.hyba.salamander.governor import CircuitState

                self.governor.worker_circuit_states["pool_primary"] = CircuitState.CLOSED
            except Exception:
                pass
        homeostasis = None
        if self.engine is not None:
            try:
                homeostasis = self.engine.check_homeostasis()
            except Exception:
                homeostasis = None
        logger.info(
            "[SALAMANDER] Heal | status=%s | errors=%s | circuit=%s",
            status,
            error_count,
            (homeostasis or {}).get("circuit_breaker_state", "CLOSED"),
        )
        return {
            "status": status,
            "protected_surface": "hyba_data.mining_subsystem",
            "engineer": "salamander",
            "homeostasis": homeostasis,
        }

    def validate_agent_action(self, action: Any, obs: Any) -> bool:
        """
        Validates a proposed TreasuryAgent action against system invariants.
        Returns True if safe, False if vetoed.
        """
        if action.execution_substrate == "igpu" and not obs.hardware_igpu_available:
            logger.warning(
                "[SALAMANDER VETO] Agent requested iGPU execution but hardware_igpu_available is False."
            )
            return False

        if obs.memory_pressure_pct > 90.0 and not action.folding_enabled:
            logger.warning("[SALAMANDER VETO] Memory pressure > 90% and folding disabled. Unsafe.")
            return False

        return True
