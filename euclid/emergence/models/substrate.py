"""Reconstructed substrate descriptions. Declared isolation is not OS enforcement."""
from __future__ import annotations
from dataclasses import dataclass, field
from .manifest import count, digest, finite, names, plain
from .telemetry import TelemetryRecord


@dataclass(frozen=True)
class SubstrateProperties:
    executor_type: str
    observation_latency: float
    action_granularity: str
    compute_substrate: str
    memory_limit_mb: int = 4096
    rng_source: str = "urandom"
    sandbox_id: str | None = None
    complexity_axis_tags: tuple[str, ...] = ()

    def __post_init__(self):
        names((self.executor_type, self.action_granularity, self.compute_substrate, self.rng_source), "substrate properties")
        finite(self.observation_latency, "observation_latency")
        count(self.memory_limit_mb, "memory_limit_mb")
        if self.memory_limit_mb == 0:
            raise ValueError("memory_limit_mb must be positive")
        object.__setattr__(self, "complexity_axis_tags", names(self.complexity_axis_tags, "tags"))

    def to_dict(self):
        return plain(self)

    def compute_id(self):
        return digest("philos.reconstructed.substrate.v1", self)


@dataclass
class SubstrateExecutionResult:
    substrate_id: str
    properties: SubstrateProperties
    iterations_completed: int
    capability_profile: dict[str, float] = field(default_factory=dict)
    telemetry_records: list[TelemetryRecord] = field(default_factory=list)
    novel_behaviors_observed: list[str] = field(default_factory=list)
    run_hash: str = ""

    def __post_init__(self):
        count(self.iterations_completed, "iterations_completed")
        if self.substrate_id != self.properties.compute_id():
            raise ValueError("substrate identity does not match properties")

    def to_dict(self):
        return plain(self)

    def compute_run_hash(self):
        payload = self.to_dict()
        payload.pop("run_hash")
        return digest("philos.reconstructed.run.v1", payload)
