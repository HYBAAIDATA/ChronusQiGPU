"""Substrate data models for indexing, isolation, and differential experimentation."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Optional


@dataclass(frozen=True)
class SubstrateProperties:
    """Hardware, execution environment, and temporal properties defining a substrate."""

    executor_type: str
    observation_latency: float  # In milliseconds
    action_granularity: str  # e.g., 'atomic', 'compositional', 'reflective'
    compute_substrate: str  # e.g., 'vm_x86_64', 'container_arm64', 'baremetal'
    memory_limit_mb: int = 4096
    rng_source: str = "urandom"
    sandbox_id: Optional[str] = None
    complexity_axis_tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not math.isfinite(self.observation_latency) or self.observation_latency < 0:
            raise ValueError("observation latency must be finite and nonnegative")
        object.__setattr__(self, "complexity_axis_tags", tuple(self.complexity_axis_tags))

    def canonical_json(self) -> str:
        payload = {
            "executor_type": self.executor_type,
            "observation_latency": round(self.observation_latency, 4),
            "action_granularity": self.action_granularity,
            "compute_substrate": self.compute_substrate,
            "memory_limit_mb": self.memory_limit_mb,
            "rng_source": self.rng_source,
            "sandbox_id": self.sandbox_id or "default",
            "complexity_axis_tags": sorted(list(self.complexity_axis_tags)),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def compute_id(self) -> str:
        """Derive a deterministic substrate ID from canonical properties."""
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:12]
        return f"sub_{self.executor_type}_{digest}"


@dataclass
class SubstrateExecutionResult:
    """Result of executing an architecture/task suite on a specific substrate."""

    substrate_id: str
    properties: SubstrateProperties
    iterations_completed: int
    capability_profile: dict[str, float] = field(default_factory=dict)
    telemetry_records: list[Any] = field(default_factory=list)
    novel_behaviors_observed: list[str] = field(default_factory=list)
    repetition_rates: dict[str, float] = field(default_factory=dict)
    run_hash: str = ""

    def __post_init__(self) -> None:
        if self.substrate_id != self.properties.compute_id():
            raise ValueError("substrate identity does not match its properties")
        if type(self.iterations_completed) is not int or self.iterations_completed < 0:
            raise ValueError("iterations_completed must be a nonnegative integer")

    def compute_run_hash(self) -> str:
        summary = {
            "hash_schema": "eqs-run-v2",
            "substrate_id": self.substrate_id,
            "iterations_completed": self.iterations_completed,
            "capability_profile": sorted(self.capability_profile.items()),
            "novel_behaviors": sorted(self.novel_behaviors_observed),
            "properties": json.loads(self.properties.canonical_json()),
            "telemetry_records": [r.to_dict() for r in self.telemetry_records],
            "repetition_rates": self.repetition_rates,
        }
        return hashlib.sha256(
            json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
        ).hexdigest()
