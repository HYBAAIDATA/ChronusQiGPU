"""CognitiveEpisode: the first-class acceptance evidence structure.

One episode records the complete arc of a reasoning attempt — identity,
representation, analogies, hypotheses, uncertainty, plan, strategies,
candidates, predictions, measured results, prediction error, attribution,
feedback, memory/strategy updates, primitive outcomes, replay lineage and
software revision.  Episodes are sealed, survive restart, and replay
deterministically whenever their components are deterministic (the sealed
core deliberately excludes wall-clock telemetry).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..contracts import domain_hash
from ..evidence import atomic_write, load_json
from .state import CognitiveState

EPISODE_SCHEMA = "euclid.cognition.episode/1"
_SEAL_DOMAIN = "euclid.cognition.episode.seal.v1"


@dataclass(frozen=True)
class CognitiveEpisode:
    episode_id: str
    problem_id: str
    goal: str
    problem_class: str
    representation: Mapping[str, Any]
    representation_hash: str
    analogies: tuple[Mapping[str, Any], ...]
    hypotheses: tuple[Mapping[str, Any], ...]
    strategies_considered: tuple[str, ...]
    selected_strategy: str | None
    strategy_basis: str
    plan: tuple[Mapping[str, Any], ...]
    candidates: tuple[Mapping[str, Any], ...]
    predictions: tuple[Mapping[str, Any], ...]
    predicted_result: str
    actual_result: Mapping[str, Any]
    prediction_errors: tuple[float, ...]
    causal_attribution: Mapping[str, Any]
    control_decisions: tuple[Mapping[str, Any], ...]
    replanning_events: tuple[Mapping[str, Any], ...]
    learning_updates: tuple[Mapping[str, Any], ...]
    memory_updates: tuple[str, ...]
    promoted_or_rejected: Mapping[str, Any]
    outcome: str
    outcome_detail: str
    replay_lineage: tuple[str, ...]
    software_revision: str
    state_payload: Mapping[str, Any]
    transition_digest: str | None
    created_at: float = field(default_factory=time.time)

    def _body(self) -> dict[str, Any]:
        return {
            "schema": EPISODE_SCHEMA,
            "episode_id": self.episode_id,
            "problem_id": self.problem_id,
            "goal": self.goal,
            "problem_class": self.problem_class,
            "representation": dict(self.representation),
            "representation_hash": self.representation_hash,
            "analogies": [dict(a) for a in self.analogies],
            "hypotheses": [dict(h) for h in self.hypotheses],
            "strategies_considered": list(self.strategies_considered),
            "selected_strategy": self.selected_strategy,
            "strategy_basis": self.strategy_basis,
            "plan": [dict(n) for n in self.plan],
            "candidates": [dict(c) for c in self.candidates],
            "predictions": [dict(p) for p in self.predictions],
            "predicted_result": self.predicted_result,
            "actual_result": dict(self.actual_result),
            "prediction_errors": list(self.prediction_errors),
            "causal_attribution": dict(self.causal_attribution),
            "control_decisions": [dict(d) for d in self.control_decisions],
            "replanning_events": [dict(e) for e in self.replanning_events],
            "learning_updates": [dict(u) for u in self.learning_updates],
            "memory_updates": list(self.memory_updates),
            "promoted_or_rejected": dict(self.promoted_or_rejected),
            "outcome": self.outcome,
            "outcome_detail": self.outcome_detail,
            "replay_lineage": list(self.replay_lineage),
            "software_revision": self.software_revision,
            "state_payload": dict(self.state_payload),
            "transition_digest": self.transition_digest,
            "created_at": self.created_at,
        }

    def to_payload(self) -> dict[str, Any]:
        body = self._body()
        return {**body, "seal": domain_hash(_SEAL_DOMAIN, body)}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CognitiveEpisode":
        body = {key: payload.get(key) for key in payload if key != "seal"}
        if body.get("schema") != EPISODE_SCHEMA:
            raise ValueError("unsupported cognitive-episode schema")
        if payload.get("seal") != domain_hash(_SEAL_DOMAIN, body):
            raise ValueError("cognitive-episode seal mismatch")
        kwargs = {key: value for key, value in body.items() if key != "schema"}
        return cls(
            **{**kwargs, "analogies": tuple(body["analogies"] or ()),
               "hypotheses": tuple(body["hypotheses"] or ()),
               "strategies_considered": tuple(body["strategies_considered"] or ()),
               "plan": tuple(body["plan"] or ()),
               "candidates": tuple(body["candidates"] or ()),
               "predictions": tuple(body["predictions"] or ()),
               "prediction_errors": tuple(float(e) for e in body["prediction_errors"] or ()),
               "control_decisions": tuple(body["control_decisions"] or ()),
               "replanning_events": tuple(body["replanning_events"] or ()),
               "learning_updates": tuple(body["learning_updates"] or ()),
               "memory_updates": tuple(body["memory_updates"] or ()),
               "replay_lineage": tuple(body["replay_lineage"] or ())}
        )

    def save(self, path: str | Path) -> None:
        atomic_write(Path(path), self.to_payload())

    @classmethod
    def load(cls, path: str | Path) -> "CognitiveEpisode":
        return cls.from_payload(load_json(Path(path)))


def episode_from_state(
    state: CognitiveState,
    *,
    goal: str,
    problem_class: str,
    strategy_basis: str,
    actual_result: Mapping[str, Any],
    causal_attribution: Mapping[str, Any],
    memory_updates: tuple[str, ...],
    promoted_or_rejected: Mapping[str, Any],
    replay_lineage: tuple[str, ...],
    software_revision: str,
    created_at: float | None = None,
) -> CognitiveEpisode:
    """Assemble the sealed episode from a completed cognitive state."""
    from dataclasses import asdict

    representation_hash = domain_hash(
        "euclid.cognition.representation.v1", state.representation
    )
    predicted = state.predictions[-1].expected if state.predictions else "none"
    episode_id = domain_hash(
        "euclid.cognition.episode-id.v1",
        {"problem_id": state.problem_id, "state_seal": state.to_payload()["seal"]},
    )
    return CognitiveEpisode(
        episode_id=episode_id,
        problem_id=state.problem_id,
        goal=goal,
        problem_class=problem_class,
        representation=state.representation,
        representation_hash=representation_hash,
        analogies=tuple(asdict(a) for a in state.analogies),
        hypotheses=tuple(
            {**asdict(h), "status": h.status.value} for h in state.hypotheses
        ),
        strategies_considered=tuple(
            ([state.selected_strategy] if state.selected_strategy else [])
            + list(state.alternative_strategies)
        ),
        selected_strategy=state.selected_strategy,
        strategy_basis=strategy_basis,
        plan=tuple(asdict(n) for n in state.plan),
        candidates=tuple(asdict(c) for c in state.candidates),
        predictions=tuple(asdict(p) for p in state.predictions),
        predicted_result=predicted,
        actual_result=dict(actual_result),
        prediction_errors=tuple(state.prediction_errors),
        causal_attribution=dict(causal_attribution),
        control_decisions=tuple(dict(d) for d in state.control_decisions),
        replanning_events=tuple(dict(e) for e in state.replanning_events),
        learning_updates=tuple(dict(u) for u in state.learning_updates),
        memory_updates=tuple(memory_updates),
        promoted_or_rejected=dict(promoted_or_rejected),
        outcome=state.outcome.value if state.outcome else "unexecuted",
        outcome_detail=state.outcome_detail,
        replay_lineage=tuple(replay_lineage),
        software_revision=software_revision,
        state_payload=state.to_payload(),
        transition_digest=state.transitions[-1].digest if state.transitions else None,
        created_at=time.time() if created_at is None else created_at,
    )


__all__ = ["CognitiveEpisode", "EPISODE_SCHEMA", "episode_from_state"]
