"""Seven-kind structured memory and the agent's long-term knowledge.

Memory kinds (``MemoryKind``): episodic (what happened), semantic
(generalised priors), procedural (abstract solution programs), primitive
(discovered operators), skill (validated compositions), strategy (which
cognitive strategies worked where) and causal (identified mechanism
structures).  Every item carries provenance; deprecation marks an item
without destroying it; retrieval ranks by structural relevance and
demonstrated transfer value, never by vocabulary.

:class:`AgentKnowledge` is everything that persists across episodes.  It can
be snapshotted and frozen, so held-out evaluation never trains on itself.
"""
from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from ...contracts import domain_hash
from ..adaptive import NoveltyArchive
from ..interfaces import MemoryItem
from ..state import MemoryKind
from ..worlds.mechanisms import DEFAULT_AGENT_KINDS
from .skills import SkillLibrary

_SEAL = "euclid.integrated.knowledge.v1"


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


class StructuralMemory:
    """MemorySystem with provenance, structural retrieval and soft deletion."""

    def __init__(self, *, retrieve_limit: int = 32) -> None:
        self.items: dict[str, MemoryItem] = {}
        self.deprecations: dict[str, str] = {}
        self.outcomes: dict[str, list[int]] = {}
        self.retrieve_limit = int(retrieve_limit)

    def retrieve(
        self, structural_features: frozenset[str], kinds: Sequence[MemoryKind] | None = None
    ) -> list[MemoryItem]:
        allowed = set(kinds or tuple(MemoryKind))
        scored = []
        for item in self.items.values():
            if item.deprecated or item.kind not in allowed:
                continue
            overlap = _jaccard(structural_features, item.structural_features)
            if overlap <= 0.0:
                continue
            successes, trials = self.outcomes.get(item.memory_id, [0, 0])
            demonstrated = (successes + 1) / (trials + 2)
            scored.append((overlap + 0.5 * demonstrated * item.transfer_value, item))
        scored.sort(key=lambda row: (-row[0], row[1].memory_id))
        return [item for _, item in scored[: self.retrieve_limit]]

    def store(self, item: MemoryItem) -> None:
        self.items[item.memory_id] = item

    def deprecate(self, memory_id: str, rationale: str) -> None:
        if memory_id not in self.items:
            raise ValueError("unknown memory")
        self.items[memory_id] = replace(self.items[memory_id], deprecated=True)
        self.deprecations[memory_id] = rationale

    def record_transfer(self, memory_id: str, success: bool) -> None:
        row = self.outcomes.setdefault(memory_id, [0, 0])
        row[0] += int(success)
        row[1] += 1

    def of_kind(self, kind: MemoryKind) -> list[MemoryItem]:
        return [i for i in self.items.values() if i.kind is kind and not i.deprecated]

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in self.items.values():
            key = item.kind.value + (":deprecated" if item.deprecated else "")
            result[key] = result.get(key, 0) + 1
        return result


class AgentKnowledge:
    """Long-term knowledge shared by every episode of one agent."""

    def __init__(self) -> None:
        self.kind_counts: dict[str, float] = {kind: 1.0 for kind in sorted(DEFAULT_AGENT_KINDS)}
        self.noise_counts: dict[str, float] = {"exact": 4.0, "noisy-low": 0.5, "noisy-high": 0.5}
        self.response_counts: dict[str, float] = {"unimodal": 1.0, "multimodal": 1.0}
        self.memory = StructuralMemory()
        self.skills = SkillLibrary()
        from .control import ContextualStrategyLearner

        self.strategies = ContextualStrategyLearner()
        self.analogy_stats: dict[str, list[float]] = {}
        self.validity: dict[str, list[float]] = {}
        self.calibration: list[tuple[float, int]] = []
        self.novelty = NoveltyArchive(threshold=0.2)
        self.transfer_ledger: list[dict[str, Any]] = []
        #: self-improvable policy parameters (see self_improvement.TUNABLE)
        self.params: dict[str, float] = {
            "analogy_mass_cap": 0.9,
            "explore_fraction": 0.3,
            "plan_samples": 3,
            "strategy_prior_weight": 2.0,
        }
        self.episodes = 0
        self.frozen = False

    # -- priors (semantic memory) ---------------------------------------------------------
    def kind_prior(self) -> dict[str, float]:
        total = sum(self.kind_counts.values())
        return {kind: count / total for kind, count in self.kind_counts.items()}

    def noise_prior(self) -> list[float]:
        names = ("exact", "noisy-low", "noisy-high")
        total = sum(self.noise_counts[n] for n in names)
        return [self.noise_counts[n] / total for n in names]

    def unimodal_prior(self) -> float:
        total = sum(self.response_counts.values())
        return self.response_counts["unimodal"] / total

    def analogy_reliability(self, bucket: str) -> float:
        successes, failures = self.analogy_stats.get(bucket, [0.0, 0.0])
        return (successes + 1.0) / (successes + failures + 2.0)

    # -- decision validity -------------------------------------------------------------------
    def record_validity(self, features: Mapping[str, float], success: bool) -> None:
        if self.frozen:
            return
        y = 1.0 if success else 0.0
        for name, value in features.items():
            row = self.validity.setdefault(name, [0.0] * 6)
            x = float(value)
            row[0] += 1.0
            row[1] += x
            row[2] += y
            row[3] += x * x
            row[4] += y * y
            row[5] += x * y

    def feature_validity(self, name: str) -> tuple[float, int]:
        """Pearson correlation of a feature with execution success, and n."""
        row = self.validity.get(name)
        if not row or row[0] < 3:
            return 0.0, int(row[0]) if row else 0
        n, sx, sy, sxx, syy, sxy = row
        cov = sxy / n - (sx / n) * (sy / n)
        vx = sxx / n - (sx / n) ** 2
        vy = syy / n - (sy / n) ** 2
        if vx <= 1e-12 or vy <= 1e-12:
            return 0.0, int(n)
        return max(-1.0, min(1.0, cov / math.sqrt(vx * vy))), int(n)

    # -- snapshots --------------------------------------------------------------------------
    def snapshot(self) -> "AgentKnowledge":
        return copy.deepcopy(self)

    def freeze(self) -> "AgentKnowledge":
        clone = self.snapshot()
        clone.frozen = True
        clone.strategies.frozen = True
        return clone

    def summary(self) -> dict[str, Any]:
        return {
            "episodes": self.episodes,
            "kind_prior": {k: round(v, 4) for k, v in self.kind_prior().items()},
            "noise_prior": [round(v, 4) for v in self.noise_prior()],
            "unimodal_prior": round(self.unimodal_prior(), 4),
            "memory": self.memory.counts(),
            "skills": self.skills.summary(),
            "strategies": self.strategies.summary(),
            "analogy_stats": {k: list(v) for k, v in sorted(self.analogy_stats.items())},
            "feature_validity": {
                name: {"correlation": round(self.feature_validity(name)[0], 4),
                       "n": self.feature_validity(name)[1]}
                for name in sorted(self.validity)
            },
            "transfer_ledger": list(self.transfer_ledger[-50:]),
            "params": dict(self.params),
            "novelty_archive": len(self.novelty.descriptors),
        }

    def to_payload(self) -> dict[str, Any]:
        body = {
            "schema": "euclid.integrated-knowledge/1",
            "kind_counts": self.kind_counts,
            "noise_counts": self.noise_counts,
            "response_counts": self.response_counts,
            "analogy_stats": self.analogy_stats,
            "validity": self.validity,
            "calibration": [list(row) for row in self.calibration],
            "transfer_ledger": self.transfer_ledger,
            "params": self.params,
            "episodes": self.episodes,
            "skills": self.skills.to_payload(),
            "strategies": self.strategies.to_payload(),
            "memory": {
                "items": [
                    {"memory_id": item.memory_id, "kind": item.kind.value,
                     "payload": dict(item.payload), "provenance": item.provenance,
                     "features": sorted(item.structural_features),
                     "transfer_value": item.transfer_value, "deprecated": item.deprecated}
                    for item in sorted(self.memory.items.values(), key=lambda i: i.memory_id)
                ],
                "deprecations": dict(sorted(self.memory.deprecations.items())),
                "outcomes": {k: list(v) for k, v in sorted(self.memory.outcomes.items())},
            },
            "novelty": [list(d) for d in self.novelty.descriptors],
        }
        return {**body, "seal": domain_hash(_SEAL, body)}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AgentKnowledge":
        body = {key: value for key, value in payload.items() if key != "seal"}
        if body.get("schema") != "euclid.integrated-knowledge/1":
            raise ValueError("unsupported knowledge schema")
        if payload.get("seal") != domain_hash(_SEAL, body):
            raise ValueError("knowledge seal mismatch")
        from .control import ContextualStrategyLearner

        knowledge = cls()
        knowledge.kind_counts = dict(body["kind_counts"])
        knowledge.noise_counts = dict(body["noise_counts"])
        knowledge.response_counts = dict(body["response_counts"])
        knowledge.analogy_stats = {k: list(v) for k, v in body["analogy_stats"].items()}
        knowledge.validity = {k: list(v) for k, v in body["validity"].items()}
        knowledge.calibration = [tuple(row) for row in body["calibration"]]
        knowledge.transfer_ledger = list(body["transfer_ledger"])
        knowledge.params = dict(body["params"])
        knowledge.episodes = int(body["episodes"])
        knowledge.skills = SkillLibrary.from_payload(body["skills"])
        knowledge.strategies = ContextualStrategyLearner.from_payload(body["strategies"])
        memory = body.get("memory") or {}
        for row in memory.get("items", ()):
            item = memory_item(row["memory_id"], MemoryKind(row["kind"]), row["payload"],
                               row["provenance"], row["features"], row["transfer_value"])
            knowledge.memory.store(replace(item, deprecated=bool(row["deprecated"])))
        knowledge.memory.deprecations = dict(memory.get("deprecations", {}))
        knowledge.memory.outcomes = {k: list(v) for k, v in memory.get("outcomes", {}).items()}
        knowledge.novelty.descriptors = [tuple(d) for d in body.get("novelty", ())]
        return knowledge


def memory_item(
    memory_id: str,
    kind: MemoryKind,
    payload: Mapping[str, Any],
    provenance: str,
    features: Iterable[str],
    transfer_value: float,
) -> MemoryItem:
    return MemoryItem(memory_id, kind, dict(payload), provenance,
                      frozenset(str(f) for f in features), float(transfer_value))


__all__ = ["AgentKnowledge", "StructuralMemory", "memory_item"]
