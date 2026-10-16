"""Substrate data models for indexing, isolation, and differential experimentation."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Optional


@dataclass(frozen=True)
class SubstrateProperties:
    """Hardware, execution environment, and temporal properties defining a substrate."""
    executor_type: str
    observation_latency: float  # In milliseconds
    action_granularity: str    # e.g., 'atomic', 'compositional', 'reflective'
    compute_substrate: str     # e.g., 'vm_x86_64', 'container_arm64', 'baremetal'
    memory_limit_mb: int = 4096
    rng_source: str = "urandom"
    sandbox_id: Optional[str] = None
    complexity_axis_tags: tuple[str, ...] = field(default_factory=tuple)

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
    capability_profile: dict[str, float]
    telemetry_records: list[Any] = field(default_factory=list)
    novel_behaviors_observed: list[str] = field(default_factory=list)
    repetition_rates: dict[str, float] = field(default_factory=dict)
    run_hash: str = ""

    def compute_run_hash(self) -> str:
        summary = {
            "substrate_id": self.substrate_id,
            "iterations_completed": self.iterations_completed,
            "capability_profile": sorted(self.capability_profile.items()),
            "novel_behaviors": sorted(self.novel_behaviors_observed),
        }
        return hashlib.sha256(
            json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
