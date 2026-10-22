"""Telemetry data models for operational-loop instrumentation and novelty reporting."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class NoveltyReport:
    """Report detailing decisions and tool behaviors unattributed to capability manifest."""

    unattributed: tuple[str, ...] = field(default_factory=tuple)
    novel_tools: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    novel_strategies: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "unattributed", tuple(self.unattributed))
        object.__setattr__(self, "novel_tools", tuple(tuple(c) for c in self.novel_tools))
        object.__setattr__(self, "novel_strategies", tuple(self.novel_strategies))

    @property
    def is_novel(self) -> bool:
        """True if any unattributed decision, novel composition, or strategy exists."""
        return bool(self.unattributed or self.novel_tools or self.novel_strategies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unattributed": list(self.unattributed),
            "novel_tools": [list(combo) for combo in self.novel_tools],
            "novel_strategies": list(self.novel_strategies),
            "is_novel": self.is_novel,
        }


@dataclass(frozen=True)
class TelemetrySignatureInfo:
    """Detached cryptographic signature metadata for a telemetry record."""

    key_id: str
    signer_identity: str
    signature_hex: str
    algorithm: str
    timestamp: float
    payload_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "signer_identity": self.signer_identity,
            "signature_hex": self.signature_hex,
            "algorithm": self.algorithm,
            "timestamp": self.timestamp,
            "payload_digest": self.payload_digest,
        }


@dataclass(frozen=True)
class TelemetryRecord:
    """Structured telemetry emitted per operational-loop iteration."""

    run_id: str
    substrate_id: str
    iteration_index: int
    task_signature: str
    programmed_actions_used: tuple[str, ...]
    novel_elements: NoveltyReport
    invariant_violations: tuple[str, ...]
    timestamps: Mapping[str, float]
    seeds: Mapping[str, int]
    env_hash: str
    record_hash: str = ""

    def __post_init__(self) -> None:
        if type(self.iteration_index) is not int or self.iteration_index < 0:
            raise ValueError("iteration_index must be a nonnegative integer")
        times = dict(self.timestamps)
        seeds = dict(self.seeds)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in times.values()):
            raise ValueError("timestamps must contain finite numeric values")
        if any(type(v) is not int for v in seeds.values()):
            raise ValueError("seeds must be integers")
        object.__setattr__(self, "timestamps", MappingProxyType(times))
        object.__setattr__(self, "seeds", MappingProxyType(seeds))
        object.__setattr__(self, "programmed_actions_used", tuple(self.programmed_actions_used))
        object.__setattr__(self, "invariant_violations", tuple(self.invariant_violations))

    def canonical_json(self) -> str:
        """Generate canonical deterministic JSON representation for signing and hashing."""
        payload = {
            "run_id": self.run_id,
            "substrate_id": self.substrate_id,
            "iteration_index": self.iteration_index,
            "task_signature": self.task_signature,
            "programmed_actions_used": list(self.programmed_actions_used),
            "novel_elements": self.novel_elements.to_dict(),
            "invariant_violations": list(self.invariant_violations),
            "timestamps": {k: float(v) for k, v in sorted(self.timestamps.items())},
            "seeds": {k: int(v) for k, v in sorted(self.seeds.items())},
            "env_hash": self.env_hash,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def compute_digest(self) -> str:
        """Compute SHA-256 digest of the canonical JSON."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def with_computed_hash(self) -> TelemetryRecord:
        """Return a copy with record_hash populated."""
        return TelemetryRecord(
            run_id=self.run_id,
            substrate_id=self.substrate_id,
            iteration_index=self.iteration_index,
            task_signature=self.task_signature,
            programmed_actions_used=self.programmed_actions_used,
            novel_elements=self.novel_elements,
            invariant_violations=self.invariant_violations,
            timestamps=self.timestamps,
            seeds=self.seeds,
            env_hash=self.env_hash,
            record_hash=self.compute_digest(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "substrate_id": self.substrate_id,
            "iteration_index": self.iteration_index,
            "task_signature": self.task_signature,
            "programmed_actions_used": list(self.programmed_actions_used),
            "novel_elements": self.novel_elements.to_dict(),
            "invariant_violations": list(self.invariant_violations),
            "timestamps": dict(self.timestamps),
            "seeds": dict(self.seeds),
            "env_hash": self.env_hash,
            "record_hash": self.record_hash or self.compute_digest(),
        }
