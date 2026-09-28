"""Scale-state classifier for the agentic mining loop.

Every state transition is evidence-backed from measured telemetry.
No fabricated thresholds, no proxy values.

State meanings:
  UNDER_UTILISED  — device has headroom; executor is waiting; safe to scale up
  HEALTHY         — operating within bounds; maintain current settings
  SATURATED       — latency or thermal boundary reached; hold, stop scaling
  OVERLOADED      — exceed bounds / recovery active; de-rate immediately
  UNCERTAIN       — missing telemetry prevents classification; hold until known
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ScaleState(StrEnum):
    UNDER_UTILISED = "UNDER_UTILISED"
    HEALTHY = "HEALTHY"
    SATURATED = "SATURATED"
    OVERLOADED = "OVERLOADED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class ScaleEvidence:
    """Measured inputs for scale classification.

    latency_bound_ms=0 or thermal_limit_c=0 means the bound is not yet
    measured; the classifier returns UNCERTAIN in that case.
    """

    kernel_latency_ms: float
    latency_bound_ms: float
    temperature_c: float
    thermal_limit_c: float
    queue_depth: int
    executor_idle_ms: float
    recovery_active: bool
    device_errors: int
    prior_throughput: float | None = None
    current_throughput: float | None = None

    def __post_init__(self) -> None:
        for name in ("kernel_latency_ms", "latency_bound_ms", "temperature_c",
                     "thermal_limit_c", "executor_idle_ms"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or float(v) < 0:
                raise ValueError(f"ScaleEvidence.{name} must be a non-negative number")
        if not isinstance(self.queue_depth, int) or self.queue_depth < 0:
            raise ValueError("queue_depth must be a non-negative integer")
        if not isinstance(self.device_errors, int) or self.device_errors < 0:
            raise ValueError("device_errors must be a non-negative integer")


@dataclass(frozen=True)
class ScaleClassification:
    state: ScaleState
    evidence: ScaleEvidence
    reason: str
    recommendation: str


class ScaleStateClassifier:
    """Classify operating state from measured evidence only.

    Thresholds are expressed as ratios of the measured bound, not
    absolute constants.  If a bound is 0 (unmeasured), the classifier
    returns UNCERTAIN — it never guesses.

    Saturation detection includes a throughput-plateau check: if
    increasing the window size produced < 5% more throughput, we are
    saturated regardless of latency.

    Recovery always overrides any other signal.
    """

    # Latency ratio thresholds
    _OVERLOADED_LATENCY = 2.0
    _SATURATED_LATENCY = 1.0
    _UNDER_UTILISED_LATENCY = 0.5

    # Thermal ratio thresholds
    _OVERLOADED_THERMAL = 1.0
    _SATURATED_THERMAL = 0.75
    _UNDER_UTILISED_THERMAL = 0.75

    # Throughput improvement threshold to declare non-plateau
    _PLATEAU_GAIN_THRESHOLD = 1.05

    def classify(self, evidence: ScaleEvidence) -> ScaleClassification:
        # Recovery and device errors always override — Salamander owns recovery.
        if evidence.recovery_active or evidence.device_errors > 0:
            return ScaleClassification(
                state=ScaleState.OVERLOADED,
                evidence=evidence,
                reason="recovery_active" if evidence.recovery_active else f"device_errors={evidence.device_errors}",
                recommendation="de_rate_stop_scaling_allow_salamander_recovery_priority",
            )

        # Missing bounds → UNCERTAIN; never scale on unmeasured bounds.
        if evidence.latency_bound_ms <= 0 or evidence.thermal_limit_c <= 0:
            return ScaleClassification(
                state=ScaleState.UNCERTAIN,
                evidence=evidence,
                reason="latency_bound_or_thermal_limit_unmeasured",
                recommendation="hold_no_scaling_decision_until_bounds_are_known",
            )

        latency_ratio = evidence.kernel_latency_ms / evidence.latency_bound_ms
        thermal_ratio = evidence.temperature_c / evidence.thermal_limit_c

        # Overloaded: latency > 2× bound OR thermal >= limit
        if latency_ratio > self._OVERLOADED_LATENCY or thermal_ratio >= self._OVERLOADED_THERMAL:
            return ScaleClassification(
                state=ScaleState.OVERLOADED,
                evidence=evidence,
                reason=(
                    f"latency_ratio={latency_ratio:.2f} "
                    f"thermal_ratio={thermal_ratio:.2f}"
                ),
                recommendation=(
                    "de_rate_cancel_speculative_windows_shorten_precompute_horizon"
                ),
            )

        # Throughput plateau: adding more window didn't help
        throughput_plateau = (
            evidence.prior_throughput is not None
            and evidence.current_throughput is not None
            and evidence.prior_throughput > 0
            and (evidence.current_throughput / evidence.prior_throughput)
            < self._PLATEAU_GAIN_THRESHOLD
        )

        # Saturated: latency > bound OR thermal > 75% OR throughput plateau
        if (
            latency_ratio > self._SATURATED_LATENCY
            or thermal_ratio > self._SATURATED_THERMAL
            or throughput_plateau
        ):
            return ScaleClassification(
                state=ScaleState.SATURATED,
                evidence=evidence,
                reason=(
                    f"latency_ratio={latency_ratio:.2f} "
                    f"thermal_ratio={thermal_ratio:.2f} "
                    f"throughput_plateau={throughput_plateau}"
                ),
                recommendation=(
                    "hold_stop_scaling_shorten_precompute_horizon"
                ),
            )

        # Under-utilised: latency well below bound AND thermal OK AND executor idle
        if (
            latency_ratio < self._UNDER_UTILISED_LATENCY
            and thermal_ratio < self._UNDER_UTILISED_THERMAL
            and evidence.executor_idle_ms > 0
        ):
            return ScaleClassification(
                state=ScaleState.UNDER_UTILISED,
                evidence=evidence,
                reason=(
                    f"latency_ratio={latency_ratio:.2f} "
                    f"thermal_ratio={thermal_ratio:.2f} "
                    f"executor_idle_ms={evidence.executor_idle_ms:.1f}"
                ),
                recommendation=(
                    "increase_precompute_depth_increase_dispatch_breadth_"
                    "activate_additional_healthy_lanes"
                ),
            )

        return ScaleClassification(
            state=ScaleState.HEALTHY,
            evidence=evidence,
            reason=(
                f"latency_ratio={latency_ratio:.2f} "
                f"thermal_ratio={thermal_ratio:.2f}"
            ),
            recommendation="maintain_current_settings",
        )
