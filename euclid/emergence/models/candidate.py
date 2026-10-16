"""Reconstructed candidate/protocol contracts; declarations are not measured evidence."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from .manifest import finite, freeze, names, plain


@dataclass(frozen=True)
class DiscoveryEnvelope:
    max_observation_latency: float
    noise_tolerance: float
    compute_budget_sec: float
    parameter_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    def __post_init__(self):
        for key in ("max_observation_latency", "noise_tolerance", "compute_budget_sec"):
            finite(getattr(self, key), key)
        for bounds in self.parameter_bounds.values():
            if len(bounds) != 2:
                raise ValueError("parameter bounds require a lower/upper pair")
            finite(bounds[0], "lower bound", float("-inf"))
            finite(bounds[1], "upper bound", float("-inf"))
            if bounds[0] > bounds[1]:
                raise ValueError("reversed parameter bounds")
        object.__setattr__(self, "parameter_bounds", freeze(self.parameter_bounds))

    def to_dict(self):
        return plain(self)

    def scale_margin(self, factor):
        finite(factor, "stress margin", 1)
        bounds = {}
        for key, (lo, hi) in self.parameter_bounds.items():
            midpoint, half = (lo + hi) / 2, (hi - lo) * factor / 2
            bounds[key] = (midpoint - half, midpoint + half)
        return DiscoveryEnvelope(self.max_observation_latency * factor,
                                 self.noise_tolerance * factor,
                                 self.compute_budget_sec / factor, bounds)


@dataclass(frozen=True)
class ReproductionProtocol:
    task_signature: str
    seed_suite: tuple[int, ...]
    manifest_hash: str
    environment_snapshot_hash: str
    required_observables: tuple[str, ...]
    statistical_tolerance: float = 0.95

    def __post_init__(self):
        names((self.task_signature, self.manifest_hash, self.environment_snapshot_hash), "protocol bindings")
        seeds = tuple(self.seed_suite)
        if not seeds or any(type(seed) is not int for seed in seeds):
            raise ValueError("seed_suite requires integer seeds")
        finite(self.statistical_tolerance, "statistical_tolerance")
        if self.statistical_tolerance > 1:
            raise ValueError("statistical_tolerance must be in [0,1]")
        object.__setattr__(self, "seed_suite", seeds)
        object.__setattr__(self, "required_observables", names(self.required_observables, "observables"))

    def to_dict(self):
        return plain(self)


@dataclass
class EmergentCandidate:
    candidate_id: str
    capability_name: str
    discovery_substrate_id: str
    discovery_envelope: DiscoveryEnvelope
    reproduction_steps: ReproductionProtocol
    claimed_behavior_signature: str = "emergent_behavior"
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self):
        names((self.candidate_id, self.capability_name, self.discovery_substrate_id,
               self.claimed_behavior_signature), "candidate identities")
        if not isinstance(self.discovery_envelope, DiscoveryEnvelope):
            raise TypeError("discovery_envelope must be DiscoveryEnvelope")
        if not isinstance(self.reproduction_steps, ReproductionProtocol):
            raise TypeError("reproduction_steps must be ReproductionProtocol")
        plain(self.baseline_metrics)

    def to_dict(self):
        return plain(self)
