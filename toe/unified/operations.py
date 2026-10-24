"""Health, self-heal, and scale.

Healing actions are the ones the platform can actually perform: re-probe a
connector, quarantine a batch over its null-rate policy, and recommend a
worker count from queue depth. Model rollback lives in the registry.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class HealAction:
    kind: str
    target: str
    detail: str
    ok: bool


@dataclass
class ScaleDecision:
    queue_depth: int
    batch_size: int
    max_workers: int
    workers: int


@dataclass
class Operations:
    max_workers: int = 8
    batch_size: int = 1000
    armed: bool = True
    queue_depth: int = 0
    probes: int = 0
    probe_failures: int = 0
    unplanned_downtime: int = 0
    ratings: list[float] = field(default_factory=list)
    last_probe_at: float | None = None
    probe_ttl_seconds: float = 60.0

    def note_probe(self, ok: bool) -> None:
        if type(ok) is not bool:
            raise TypeError("probe result must be a measured boolean")
        self.last_probe_at = time.monotonic()
        self.probes += 1
        if not ok:
            self.probe_failures += 1

    def note_rating(self, score: float) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError("rating must be between 0 and 1")
        self.ratings.append(score)

    def probes_fresh(self) -> bool:
        return (self.last_probe_at is not None and self.probes > 0
                and 0 <= time.monotonic() - self.last_probe_at <= self.probe_ttl_seconds)

    def availability(self) -> float | None:
        if self.probes == 0:
            return None
        return (self.probes - self.probe_failures) / self.probes

    def satisfaction(self) -> float | None:
        if not self.ratings:
            return None
        return sum(self.ratings) / len(self.ratings)

    def scale(self) -> ScaleDecision:
        if self.batch_size < 1 or self.max_workers < 1:
            raise ValueError("batch_size and max_workers must be >= 1")
        if self.queue_depth < 0:
            raise ValueError("queue_depth must be >= 0")
        needed = math.ceil(self.queue_depth / self.batch_size) if self.queue_depth else 1
        workers = max(1, min(self.max_workers, needed))
        return ScaleDecision(self.queue_depth, self.batch_size, self.max_workers, workers)

    def heal(self, platform: "PlatformHooks") -> list[HealAction]:
        actions: list[HealAction] = []
        for connector_id, bound in list(platform.connections().items()):
            try:
                probe = bound.probe()
                # Driver preflight/configuration checks are NOT availability.
                if probe.measured:
                    platform.operations_note(probe.ok)
                actions.append(HealAction("reprobe", connector_id, probe.detail, probe.ok))
            except Exception as exc:
                platform.operations_note(False)
                actions.append(HealAction("reprobe", connector_id, str(exc), False))
        for entity in platform.entities():
            policy = platform.null_policy(entity)
            for batch_id in platform.batches(entity):
                if platform.batch_null_rate(batch_id) > policy:
                    quarantined = platform.quarantine(batch_id)
                    if quarantined:
                        actions.append(
                            HealAction("quarantine", batch_id, f"{entity} null rate over {policy}", True)
                        )
        if not actions:
            actions.append(HealAction("none", "platform", "no degraded connector or dirty batch", True))
        return actions


class PlatformHooks:
    def connections(self) -> dict:
        raise NotImplementedError

    def operations_note(self, ok: bool) -> None:
        raise NotImplementedError

    def entities(self) -> list[str]:
        raise NotImplementedError

    def quality(self, entity: str):
        raise NotImplementedError

    def null_policy(self, entity: str) -> float:
        raise NotImplementedError

    def batches(self, entity: str) -> list[str]:
        raise NotImplementedError

    def quarantine(self, batch_id: str) -> int:
        raise NotImplementedError
