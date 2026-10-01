"""Observed-only self-optimizing tuner for the PYTHIA control plane.

The tuner proposes mathematically valid execution plans from observed thermal,
latency, power, and hashing counters. It never dispatches OpenCL work, claims
an H/s improvement, validates a share, or prunes a nonce without an injected
independent proof verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from turing_core import TuringScheduleError, complete_nonce_schedule, validate_schedule


class OptimizationRejected(RuntimeError):
    """The observed optimization request cannot be safely applied."""


@dataclass(frozen=True)
class OptimizationObservation:
    kernel_latency_ms: float
    latency_bound_ms: float
    temperature_c: float
    thermal_limit_c: float
    hashes_computed: int
    elapsed_seconds: float
    power_w: float
    stratum_state: str
    new_job_observed: bool
    observed_at_ns: int

    @classmethod
    def from_telemetry(
        cls, telemetry: Mapping[str, Any], *, observed_at_ns: int
    ) -> "OptimizationObservation":
        required = {
            "kernel_latency_ms",
            "kernel_latency_bound_ms",
            "temperature_c",
            "thermal_limit_c",
            "hashes_computed",
            "elapsed_seconds",
            "power_w",
            "stratum_state",
            "new_job_observed",
        }
        missing = sorted(required.difference(telemetry))
        if missing:
            raise OptimizationRejected(f"missing observed telemetry: {', '.join(missing)}")
        numeric = {key: telemetry[key] for key in required - {"stratum_state", "new_job_observed"}}
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in numeric.values()
        ):
            raise OptimizationRejected("numeric optimization telemetry is malformed")
        if any(float(value) < 0 for value in numeric.values()):
            raise OptimizationRejected("optimization telemetry cannot be negative")
        if float(telemetry["elapsed_seconds"]) <= 0 or int(telemetry["hashes_computed"]) < 0:
            raise OptimizationRejected("measured elapsed time and hash count are required")
        if not isinstance(telemetry["stratum_state"], str) or not telemetry["stratum_state"]:
            raise OptimizationRejected("observed Stratum state is required")
        if not isinstance(telemetry["new_job_observed"], bool) or observed_at_ns <= 0:
            raise OptimizationRejected("observed transition metadata is malformed")
        return cls(
            kernel_latency_ms=float(telemetry["kernel_latency_ms"]),
            latency_bound_ms=float(telemetry["kernel_latency_bound_ms"]),
            temperature_c=float(telemetry["temperature_c"]),
            thermal_limit_c=float(telemetry["thermal_limit_c"]),
            hashes_computed=int(telemetry["hashes_computed"]),
            elapsed_seconds=float(telemetry["elapsed_seconds"]),
            power_w=float(telemetry["power_w"]),
            stratum_state=telemetry["stratum_state"],
            new_job_observed=telemetry["new_job_observed"],
            observed_at_ns=observed_at_ns,
        )

    @property
    def measured_hashrate(self) -> float:
        return self.hashes_computed / self.elapsed_seconds

    @property
    def measured_hashrate_per_watt(self) -> float:
        if self.power_w <= 0:
            return 0.0
        return self.measured_hashrate / self.power_w


@dataclass(frozen=True)
class WorkGroupPlan:
    global_size: int
    local_size: int
    chunk_size: int
    reason: str
    evidence: Mapping[str, float | int | str]

    def __post_init__(self) -> None:
        if min(self.global_size, self.local_size, self.chunk_size) <= 0:
            raise OptimizationRejected("work-group dimensions must be positive")
        if self.global_size % self.local_size != 0:
            raise OptimizationRejected("global size must be divisible by local size")
        if not self.reason:
            raise OptimizationRejected("work-group plan requires a reason")
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True)
class ExclusionCertificate:
    excluded_nonces: tuple[int, ...]
    proof_reference: str
    target_fingerprint: str
    complete_coverage_preserved: bool


@dataclass(frozen=True)
class SchedulePlan:
    nonces: tuple[int, ...]
    window: int
    seed: int
    pruning_applied: bool
    excluded_nonces: tuple[int, ...]
    proof_reference: str | None


ProofVerifier = Callable[[ExclusionCertificate, int], bool]


class SelfOptimizingTuner:
    """Generate bounded plans from measured telemetry and verified evidence."""

    def __init__(self, *, max_local_size: int = 1024, max_global_size: int = 1 << 20) -> None:
        if max_local_size <= 0 or max_global_size <= 0:
            raise ValueError("work-group limits must be positive")
        self.max_local_size = max_local_size
        self.max_global_size = max_global_size

    def suggest_workgroup(
        self,
        observation: OptimizationObservation,
        *,
        current: WorkGroupPlan,
    ) -> WorkGroupPlan:
        """Suggest dimensions; the OpenCL driver must validate and dispatch them."""
        if current.local_size > self.max_local_size or current.global_size > self.max_global_size:
            raise OptimizationRejected("current work-group exceeds device contract")
        if observation.new_job_observed or observation.stratum_state in {"NEW_JOB", "STALE"}:
            return WorkGroupPlan(
                global_size=current.global_size,
                local_size=current.local_size,
                chunk_size=current.chunk_size,
                reason="hold dimensions while live Stratum work transitions",
                evidence={"stratum_state": observation.stratum_state},
            )
        overloaded = (
            observation.kernel_latency_ms > observation.latency_bound_ms
            or observation.temperature_c >= observation.thermal_limit_c
        )
        if overloaded:
            local = max(1, current.local_size // 2)
            global_size = max(local, (current.global_size // 2 // local) * local)
            global_size = max(local, global_size)
            chunk = max(1, current.chunk_size // 2)
            reason = "reduce observed thermal or latency load"
        elif (
            observation.kernel_latency_ms <= observation.latency_bound_ms / 2
            and observation.temperature_c < observation.thermal_limit_c * 0.75
            and observation.measured_hashrate_per_watt > 0
        ):
            local = min(self.max_local_size, max(1, current.local_size * 2))
            global_size = min(self.max_global_size, current.global_size * 2)
            global_size = max(local, (global_size // local) * local)
            chunk = current.chunk_size * 2
            reason = "increase bounded dimensions under observed thermal and latency headroom"
        else:
            local, global_size, chunk, reason = (
                current.local_size,
                current.global_size,
                current.chunk_size,
                "retain dimensions within observed operating bounds",
            )
        return WorkGroupPlan(
            global_size=global_size,
            local_size=local,
            chunk_size=chunk,
            reason=reason,
            evidence={
                "kernel_latency_ms": observation.kernel_latency_ms,
                "temperature_c": observation.temperature_c,
                "measured_hashrate_per_watt": observation.measured_hashrate_per_watt,
            },
        )

    def schedule(
        self,
        *,
        window: int,
        seed: int,
        certificate: ExclusionCertificate | None = None,
        proof_verifier: ProofVerifier | None = None,
    ) -> SchedulePlan:
        """Return a complete Turing permutation or an independently verified subset."""
        if window < 0:
            raise OptimizationRejected("schedule window cannot be negative")
        try:
            ordered = complete_nonce_schedule(window, seed=seed)
        except TuringScheduleError as exc:
            raise OptimizationRejected(str(exc)) from exc
        if certificate is None:
            return SchedulePlan(ordered, window, seed, False, (), None)
        if proof_verifier is None:
            raise OptimizationRejected("pruning requires an independent proof verifier")
        if not certificate.proof_reference or not certificate.target_fingerprint:
            raise OptimizationRejected("pruning certificate requires proof and target references")
        if not certificate.complete_coverage_preserved:
            raise OptimizationRejected("pruning certificate does not preserve acceptance coverage")
        excluded = tuple(certificate.excluded_nonces)
        if len(set(excluded)) != len(excluded) or any(n < 0 or n >= window for n in excluded):
            raise OptimizationRejected("pruning certificate contains invalid nonces")
        if not proof_verifier(certificate, window):
            raise OptimizationRejected("independent pruning verifier rejected certificate")
        remaining = tuple(nonce for nonce in ordered if nonce not in set(excluded))
        validate_schedule(remaining, window, require_complete=False)
        return SchedulePlan(remaining, window, seed, True, excluded, certificate.proof_reference)
