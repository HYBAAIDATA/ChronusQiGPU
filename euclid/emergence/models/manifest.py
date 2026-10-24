"""Capability manifest model defining declared actions, compositions, and strategies."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class CapabilityManifest:
    """Declared capability baseline for an agent.

    Any action, composition, or strategy outside this manifest is evaluated
    as potential novel emergent behavior.
    """

    declared_actions: frozenset[str] = field(default_factory=frozenset)
    declared_compositions: frozenset[tuple[str, ...]] = field(default_factory=frozenset)
    declared_strategies: frozenset[str] = field(default_factory=frozenset)
    version: str = "1.0.0"
    manifest_id: str = "manifest-default"

    def __post_init__(self) -> None:
        object.__setattr__(self, "declared_actions", frozenset(self.declared_actions))
        object.__setattr__(
            self,
            "declared_compositions",
            frozenset(tuple(composition) for composition in self.declared_compositions),
        )
        object.__setattr__(self, "declared_strategies", frozenset(self.declared_strategies))

    def compute_hash(self) -> str:
        """Deterministic SHA-256 fingerprint of the declared manifest."""
        canonical_repr = {
            "manifest_id": self.manifest_id,
            "version": self.version,
            "actions": sorted(list(self.declared_actions)),
            "compositions": sorted([list(c) for c in self.declared_compositions]),
            "strategies": sorted(list(self.declared_strategies)),
        }
        encoded = json.dumps(canonical_repr, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "version": self.version,
            "hash": self.compute_hash(),
            "declared_actions": sorted(list(self.declared_actions)),
            "declared_compositions": [list(c) for c in self.declared_compositions],
            "declared_strategies": sorted(list(self.declared_strategies)),
        }
