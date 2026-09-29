"""Evidence gate between measured executions and ``SelfOptimizingTuner``.

The tuner is consulted only when every input it needs was measured. Its
output may change only future work: the next SearchPlan window (HOW MUCH)
and a workgroup recommendation that is reported, never claimed as applied,
because the CPU/MMIO path exposes no workgroup register.

Precedence: recovery > missing evidence > Stratum transition > tuner.
No decision ever claims an improvement; that needs a post-change measurement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .self_optimizing_agent import (
    OptimizationObservation,
    OptimizationRejected,
    SelfOptimizingTuner,
    WorkGroupPlan,
)

_LOCAL = 32


@dataclass(frozen=True)
class TuningDecision:
    action: str
    reason: str
    next_window: int
    missing: tuple[str, ...] = ()
    workgroup: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    improvement_claimed: bool = False


class TuningGate:
    def __init__(
        self,
        tuner: SelfOptimizingTuner | None = None,
        *,
        latency_bound_ms: float | None = None,
        thermal_limit_c: float | None = None,
        temperature_probe: Callable[[], float | None] | None = None,
        power_probe: Callable[[], float | None] | None = None,
        workgroup_supported: bool = False,
    ) -> None:
        self.tuner = tuner or SelfOptimizingTuner()
        self.latency_bound_ms = latency_bound_ms
        self.thermal_limit_c = thermal_limit_c
        self.temperature_probe = temperature_probe
        self.power_probe = power_probe
        self.workgroup_supported = workgroup_supported
        self.last_decision: TuningDecision | None = None

    @staticmethod
    def _probe(probe: Callable[[], float | None] | None) -> float | None:
        if probe is None:
            return None
        try:
            value = probe()
        except Exception:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return None
        return float(value)

    def evaluate(
        self,
        *,
        current_window: int,
        max_window: int,
        kernel_latency_ms: float,
        hashes_computed: int,
        elapsed_seconds: float,
        new_job_observed: bool,
        stratum_state: str,
        recovery_active: bool,
    ) -> TuningDecision:
        current_window = max(1, min(current_window, max_window))
        if recovery_active:
            return self._hold(current_window, "recovery overrides optimisation")
        temperature = self._probe(self.temperature_probe)
        power = self._probe(self.power_probe)
        measured = {
            "kernel_latency_bound_ms": self.latency_bound_ms,
            "thermal_limit_c": self.thermal_limit_c,
            "temperature_c": temperature,
            "power_w": power,
        }
        missing = tuple(sorted(k for k, v in measured.items() if v is None))
        if elapsed_seconds <= 0 or hashes_computed <= 0:
            missing += ("hashes_computed/elapsed_seconds",)
        if missing:
            return self._hold(current_window, "missing measured bounds", missing)
        telemetry = {
            **measured,
            "kernel_latency_ms": kernel_latency_ms,
            "hashes_computed": hashes_computed,
            "elapsed_seconds": elapsed_seconds,
            "stratum_state": stratum_state,
            "new_job_observed": new_job_observed,
        }
        current = WorkGroupPlan(
            global_size=-(-current_window // _LOCAL) * _LOCAL,
            local_size=_LOCAL,
            chunk_size=current_window,
            reason="current plan window",
            evidence={},
        )
        try:
            observation = OptimizationObservation.from_telemetry(
                telemetry, observed_at_ns=time.monotonic_ns()
            )
            suggestion = self.tuner.suggest_workgroup(observation, current=current)
        except OptimizationRejected as exc:
            return self._hold(current_window, f"tuner rejected evidence: {exc}")
        proposed = max(1, min(suggestion.chunk_size, max_window))
        if new_job_observed and proposed > current_window:
            proposed = current_window
        action = (
            "DE_RATE"
            if proposed < current_window
            else "SCALE_UP" if proposed > current_window else "RETAIN"
        )
        decision = TuningDecision(
            action=action,
            reason=suggestion.reason,
            next_window=proposed,
            workgroup={
                "requested": {
                    "global_size": suggestion.global_size,
                    "local_size": suggestion.local_size,
                },
                "supported": self.workgroup_supported,
                "executed": False,
            },
            evidence=dict(suggestion.evidence),
        )
        self.last_decision = decision
        return decision

    def _hold(self, window: int, reason: str, missing: tuple[str, ...] = ()) -> TuningDecision:
        decision = TuningDecision("HOLD", reason, window, missing)
        self.last_decision = decision
        return decision
