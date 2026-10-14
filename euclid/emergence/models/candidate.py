"""Candidate and envelope models for emergent behavior qualification."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Optional


@dataclass(frozen=True)
class DiscoveryEnvelope:
    """Operating conditions and parameter boundaries under which a behavior was discovered."""
    max_observation_latency: float  # ms
    noise_tolerance: float         # 0.0 to 1.0 (fraction of noise injected)
    compute_budget_sec: float      # compute time per decision
    parameter_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)

    def scale_margin(self, margin: float) -> DiscoveryEnvelope:
        """Expand the stress envelope by a given margin multiplier (e.g. 1.5x)."""
        expanded_bounds = {}
        for k, (low, high) in self.parameter_bounds.items():
            span = high - low
            mid = (high + low) / 2.0
            expanded_span = span * margin
            expanded_bounds[k] = (mid - expanded_span / 2.0, mid + expanded_span / 2.0)

        return DiscoveryEnvelope(
            max_observation_latency=self.max_observation_latency * margin,
            noise_tolerance=min(1.0, self.noise_tolerance * margin),
            compute_budget_sec=self.compute_budget_sec / margin if margin > 0 else self.compute_budget_sec,
            parameter_bounds=expanded_bounds,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_observation_latency": self.max_observation_latency,
            "noise_tolerance": self.noise_tolerance,
            "compute_budget_sec": self.compute_budget_sec,
            "parameter_bounds": {k: list(v) for k, v in self.parameter_bounds.items()},
        }


@dataclass(frozen=True)
class ReproductionProtocol:
    """Strict protocol specifying the exact conditions and observables for independent reproduction."""
    task_signature: str
    seed_suite: tuple[int, ...]
    manifest_hash: str
    environment_snapshot_hash: str
    required_observables: tuple[str, ...]
    statistical_tolerance: float = 0.95  # Minimum required reproduction rate
    steps: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def compute_protocol_hash(self) -> str:
        payload = {
            "task_signature": self.task_signature,
            "seed_suite": list(self.seed_suite),
            "manifest_hash": self.manifest_hash,
            "environment_snapshot_hash": self.environment_snapshot_hash,
            "required_observables": sorted(list(self.required_observables)),
            "statistical_tolerance": self.statistical_tolerance,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_hash": self.compute_protocol_hash(),
            "task_signature": self.task_signature,
            "seed_suite": list(self.seed_suite),
            "manifest_hash": self.manifest_hash,
            "environment_snapshot_hash": self.environment_snapshot_hash,
            "required_observables": list(self.required_observables),
            "statistical_tolerance": self.statistical_tolerance,
            "step_count": len(self.steps),
        }


@dataclass
class EmergentCandidate:
    """Candidate emergent capability proposed for qualification."""
    candidate_id: str
    capability_name: str
    discovery_substrate_id: str
    discovery_envelope: DiscoveryEnvelope
    reproduction_steps: ReproductionProtocol
    claimed_behavior_signature: str
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    source: Optional[str] = None  # Composed source model representation in recursive folding
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        payload = {
            "candidate_id": self.candidate_id,
            "capability_name": self.capability_name,
            "discovery_substrate_id": self.discovery_substrate_id,
            "discovery_envelope": self.discovery_envelope.to_dict(),
            "reproduction_protocol_hash": self.reproduction_steps.compute_protocol_hash(),
            "claimed_behavior_signature": self.claimed_behavior_signature,
            "baseline_metrics": sorted(self.baseline_metrics.items()),
            "source": self.source or "root",
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
