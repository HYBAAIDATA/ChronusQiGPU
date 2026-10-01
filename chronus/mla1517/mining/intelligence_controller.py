"""Observed-only intelligence control signals for the PYTHIA coordinator.

The controller reads immutable TOE context and telemetry snapshots. It does not
hash, validate, submit, or manufacture mining work. Every signal is advisory
control-plane output; the canonical adapters remain authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from .toe_context import TOEContext, TOEContextUnavailable

MODEL_VERSIONS = {
    "intelligence_controller": "1.1.0",
    "ntime_anomaly_detector": "1.0.0",
}


class ControlCommand(StrEnum):
    HOLD = "HOLD"
    FLUSH_LANE = "FLUSH_LANE"
    RESIZE_WORKGROUP = "RESIZE_WORKGROUP"
    PRUNE_WINDOW = "PRUNE_WINDOW"
    PAUSE = "PAUSE"


@dataclass(frozen=True)
class ControlSignal:
    """Stable ABI for deterministic control-plane decisions."""

    command: ControlCommand
    reason: str
    observed_at_ns: int
    source_sequence: int
    job_id: str
    parameters: Mapping[str, Any]
    evidence: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.observed_at_ns <= 0 or self.source_sequence < 0 or not self.job_id:
            raise ValueError("control signal requires observed coordinates and job id")
        if not self.reason:
            raise ValueError("control signal reason is required")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True)
class ControllerDecision:
    """One immutable decision batch derived from one observed snapshot."""

    signals: tuple[ControlSignal, ...]
    observation: Mapping[str, Any]


class IntelligenceController:
    """Classify observed operating conditions into deterministic signals."""

    def __init__(
        self,
        *,
        default_latency_bound_ms: float = 100.0,
        default_thermal_limit_c: float = 85.0,
        default_ntime_tolerance_seconds: int = 7_200,
    ) -> None:
        if (
            default_latency_bound_ms <= 0
            or default_thermal_limit_c <= 0
            or default_ntime_tolerance_seconds < 0
        ):
            raise ValueError("controller bounds must be non-negative/positive")
        self.default_latency_bound_ms = float(default_latency_bound_ms)
        self.default_thermal_limit_c = float(default_thermal_limit_c)
        self.default_ntime_tolerance_seconds = int(default_ntime_tolerance_seconds)

    @staticmethod
    def _number(snapshot: Mapping[str, Any], key: str, default: float) -> float:
        value = snapshot.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TOEContextUnavailable(f"telemetry field {key!r} must be numeric")
        return float(value)

    def _ntime_anomaly(self, snapshot: Mapping[str, Any]) -> tuple[bool, float | None]:
        explicit = snapshot.get("ntime_anomaly")
        if explicit is not None:
            if not isinstance(explicit, bool):
                raise TOEContextUnavailable("telemetry field 'ntime_anomaly' must be boolean")
            delta = snapshot.get("ntime_delta_seconds")
            if delta is not None and (
                isinstance(delta, bool) or not isinstance(delta, (int, float))
            ):
                raise TOEContextUnavailable("telemetry field 'ntime_delta_seconds' must be numeric")
            return explicit, float(delta) if delta is not None else None
        current = snapshot.get("ntime")
        reference = snapshot.get("job_ntime")
        if current is None or reference is None:
            return False, None
        if isinstance(current, bool) or isinstance(reference, bool):
            raise TOEContextUnavailable("ntime values must be numeric")
        if not isinstance(current, (int, float)) or not isinstance(reference, (int, float)):
            raise TOEContextUnavailable("ntime values must be numeric")
        delta = float(current) - float(reference)
        tolerance = self._number(
            snapshot,
            "ntime_tolerance_seconds",
            self.default_ntime_tolerance_seconds,
        )
        if tolerance < 0:
            raise TOEContextUnavailable("ntime tolerance cannot be negative")
        return abs(delta) > tolerance, delta

    @staticmethod
    def _signal(
        *,
        command: ControlCommand,
        reason: str,
        context: TOEContext,
        observed_at_ns: int,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> ControlSignal:
        return ControlSignal(
            command=command,
            reason=reason,
            observed_at_ns=observed_at_ns,
            source_sequence=context.sequence,
            job_id=str(context.stratum_job["job_id"]),
            parameters=parameters,
            evidence=evidence,
        )

    def evaluate(
        self,
        *,
        context: TOEContext,
        telemetry: Mapping[str, Any],
        observed_at_ns: int,
    ) -> ControllerDecision:
        """Evaluate one observed snapshot without mutating any feed."""
        if context.synthetic:
            raise TOEContextUnavailable("synthetic context cannot drive control")
        if observed_at_ns <= 0:
            raise ValueError("observed_at_ns must be positive")
        if not isinstance(telemetry, Mapping) or not telemetry:
            raise TOEContextUnavailable("read-only telemetry snapshot is required")

        snapshot = dict(telemetry)
        latency = self._number(snapshot, "kernel_latency_ms", 0.0)
        latency_bound = self._number(
            snapshot, "kernel_latency_bound_ms", self.default_latency_bound_ms
        )
        temperature = self._number(snapshot, "temperature_c", 0.0)
        thermal_limit = self._number(snapshot, "thermal_limit_c", self.default_thermal_limit_c)
        stratum_state = snapshot.get("stratum_state", "READY")
        new_job = bool(snapshot.get("new_job_observed", False))
        ntime_anomaly, ntime_delta = self._ntime_anomaly(snapshot)
        evidence = {
            "kernel_latency_ms": latency,
            "kernel_latency_bound_ms": latency_bound,
            "temperature_c": temperature,
            "thermal_limit_c": thermal_limit,
            "stratum_state": stratum_state,
            "new_job_observed": new_job,
            "ntime_anomaly": ntime_anomaly,
            "ntime_delta_seconds": ntime_delta,
            "model_versions": dict(MODEL_VERSIONS),
        }
        signals: list[ControlSignal] = []

        if ntime_anomaly:
            signals.append(
                self._signal(
                    command=ControlCommand.PAUSE,
                    reason="observed ntime anomaly requires conservative work reduction",
                    context=context,
                    observed_at_ns=observed_at_ns,
                    parameters={"action": "pause_and_revalidate_job"},
                    evidence=evidence,
                )
            )
        if new_job or stratum_state in {"NEW_JOB", "STALE"}:
            signals.append(
                self._signal(
                    command=ControlCommand.FLUSH_LANE,
                    reason="live Stratum job transition requires stale-work severance",
                    context=context,
                    observed_at_ns=observed_at_ns,
                    parameters={"job_id": context.stratum_job["job_id"]},
                    evidence=evidence,
                )
            )
        else:
            if latency > latency_bound * 2.0:
                signals.append(
                    self._signal(
                        command=ControlCommand.FLUSH_LANE,
                        reason="observed kernel latency exceeds hang bound",
                        context=context,
                        observed_at_ns=observed_at_ns,
                        parameters={"action": "restart_lane_after_ack"},
                        evidence=evidence,
                    )
                )
            elif latency > latency_bound:
                signals.append(
                    self._signal(
                        command=ControlCommand.RESIZE_WORKGROUP,
                        reason="observed kernel latency exceeds operating bound",
                        context=context,
                        observed_at_ns=observed_at_ns,
                        parameters={"direction": "down", "factor": 2},
                        evidence=evidence,
                    )
                )

            if temperature >= thermal_limit:
                signals.append(
                    self._signal(
                        command=ControlCommand.RESIZE_WORKGROUP,
                        reason="observed thermal telemetry exceeds configured limit",
                        context=context,
                        observed_at_ns=observed_at_ns,
                        parameters={"direction": "down", "factor": 2},
                        evidence=evidence,
                    )
                )

            exclusion = snapshot.get("proven_exclusion")
            if isinstance(exclusion, Mapping):
                if (
                    exclusion.get("complete_coverage_preserved") is True
                    and exclusion.get("proof_reference")
                    and exclusion.get("excluded_count", 0) >= 0
                ):
                    signals.append(
                        self._signal(
                            command=ControlCommand.PRUNE_WINDOW,
                            reason="independently proven exclusion permits schedule pruning",
                            context=context,
                            observed_at_ns=observed_at_ns,
                            parameters={
                                "proof_reference": exclusion["proof_reference"],
                                "excluded_count": int(exclusion["excluded_count"]),
                            },
                            evidence=evidence,
                        )
                    )

        if not signals:
            signals.append(
                self._signal(
                    command=ControlCommand.HOLD,
                    reason="observed telemetry is within configured operating bounds",
                    context=context,
                    observed_at_ns=observed_at_ns,
                    parameters={},
                    evidence=evidence,
                )
            )
        return ControllerDecision(
            signals=tuple(signals),
            observation=context.observation(),
        )
