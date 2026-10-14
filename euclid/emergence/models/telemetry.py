"""Reconstructed immutable telemetry payloads; local signatures are not attestation."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Mapping
from .manifest import canonical, count, digest, finite, freeze, names, plain


@dataclass(frozen=True)
class NoveltyReport:
    unattributed: tuple[str, ...] = ()
    novel_tools: tuple[tuple[str, ...], ...] = ()
    novel_strategies: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "unattributed", names(self.unattributed, "unattributed"))
        object.__setattr__(self, "novel_tools", tuple(names(t, "tool composition") for t in self.novel_tools))
        object.__setattr__(self, "novel_strategies", names(self.novel_strategies, "strategies"))

    @property
    def is_novel(self):
        return bool(self.unattributed or self.novel_tools or self.novel_strategies)

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class TelemetrySignatureInfo:
    key_id: str
    signer_identity: str
    signature_hex: str
    algorithm: str
    timestamp: float
    payload_digest: str

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class TelemetryRecord:
    run_id: str
    substrate_id: str
    iteration_index: int
    task_signature: str
    programmed_actions_used: tuple[str, ...]
    novel_elements: NoveltyReport
    invariant_violations: tuple[str, ...] = ()
    timestamps: Mapping[str, float] = field(default_factory=dict)
    seeds: Mapping[str, int] = field(default_factory=dict)
    env_hash: str = ""
    record_hash: str = ""

    def __post_init__(self):
        names((self.run_id, self.substrate_id, self.task_signature), "telemetry identities")
        count(self.iteration_index, "iteration_index")
        if not isinstance(self.novel_elements, NoveltyReport):
            raise TypeError("novel_elements must be NoveltyReport")
        for value in self.timestamps.values():
            finite(value, "timestamp")
        for value in self.seeds.values():
            if type(value) is not int:
                raise ValueError("seeds must be integers")
        object.__setattr__(self, "programmed_actions_used", names(self.programmed_actions_used, "actions"))
        object.__setattr__(self, "invariant_violations", names(self.invariant_violations, "violations"))
        object.__setattr__(self, "timestamps", freeze(self.timestamps))
        object.__setattr__(self, "seeds", freeze(self.seeds))

    def to_dict(self):
        return plain(self)

    def _payload(self):
        payload = self.to_dict()
        payload.pop("record_hash")
        return payload

    def canonical_json(self):
        return canonical(self._payload())

    def compute_digest(self):
        return digest("philos.reconstructed.telemetry.v1", self._payload())

    def with_computed_hash(self):
        return replace(self, record_hash=self.compute_digest())
