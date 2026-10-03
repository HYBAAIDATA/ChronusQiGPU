"""Executable capability reachability ledger.

No capability is called integrated before FEEDBACK_CLOSED.  Runtime probes are
append-only evidence entries and can be persisted/reloaded as JSON.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Mapping


class ReachabilityStage(IntEnum):
    PRESENT = 0
    IMPORTABLE = 1
    ADAPTED = 2
    REGISTERED = 3
    REACHABLE = 4
    USED_IN_EPISODE = 5
    CHANGES_DECISION = 6
    EXECUTED = 7
    OUTCOME_OBSERVED = 8
    FEEDBACK_CLOSED = 9
    PERSISTED = 10
    RESTART_VERIFIED = 11
    TRANSFER_VERIFIED = 12


@dataclass(frozen=True)
class CapabilityEvidence:
    component: str
    stage: str
    episode_id: str
    evidence_ref: str
    detail: Mapping[str, Any]


class ReachabilityMatrix:
    def __init__(self) -> None:
        self._entries: list[CapabilityEvidence] = []

    def record(
        self, component: str, stage: ReachabilityStage, *,
        episode_id: str, evidence_ref: str, detail: Mapping[str, Any] | None = None,
    ) -> CapabilityEvidence:
        current = self.stage(component)
        if current is not None and stage < current:
            raise ValueError("capability reachability cannot move backwards")
        entry = CapabilityEvidence(
            component, stage.name, episode_id, evidence_ref, dict(detail or {})
        )
        self._entries.append(entry)
        return entry

    def stage(self, component: str) -> ReachabilityStage | None:
        names = [e.stage for e in self._entries if e.component == component]
        return ReachabilityStage[names[-1]] if names else None

    def integrated(self, component: str) -> bool:
        stage = self.stage(component)
        return stage is not None and stage >= ReachabilityStage.FEEDBACK_CLOSED

    def require(self, component: str, stage: ReachabilityStage) -> None:
        actual = self.stage(component)
        if actual is None or actual < stage:
            raise AssertionError(
                f"{component} reached {actual.name if actual else 'NONE'}, "
                f"requires {stage.name}"
            )

    def save(self, path: str | Path) -> None:
        payload = {
            "schema": "euclid.cognition.reachability/1",
            "entries": [asdict(entry) for entry in self._entries],
        }
        Path(path).write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "ReachabilityMatrix":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema") != "euclid.cognition.reachability/1":
            raise ValueError("unsupported reachability schema")
        matrix = cls()
        matrix._entries = [
            CapabilityEvidence(**entry) for entry in payload.get("entries", ())
        ]
        return matrix


__all__ = ["CapabilityEvidence", "ReachabilityMatrix", "ReachabilityStage"]