"""Kairos Mining-Orchestration Reasoning Layer — stability-first laboratory slice.

It derives bounded, deterministic research indicators from explicitly supplied
laboratory observations. It has no miner, pool, wallet, credential, network,
share submission, performance, revenue, or profitability capability.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Mapping
from .kairos_execution import KairosExecutionLayer
from .kairos_runtime import FoldOutcome

@dataclass(frozen=True)
class StabilityObservation:
    observation_id: str
    risk: float
    volatility: float
    forbidden_state: bool = False
    anomaly_signal: float = 0.0
    agent_labels: tuple[str, ...] = ()

@dataclass(frozen=True)
class StabilityAssessment:
    observation_id: str
    posture: str
    predicted_volatility: float
    forbidden_state_likelihood: float
    anomaly_detected: bool
    resilience_score: float
    policy_proposal: str
    accepted: bool
    chronicle_event_hash: str | None
    claim_boundary: str

class StabilityReasoningModule:
    """Fail-closed stability assessment for a sealed laboratory world."""
    def __init__(self, layer: KairosExecutionLayer | None = None) -> None:
        self.layer = layer or KairosExecutionLayer()
        self._history: list[StabilityObservation] = []

    def assess(self, world_id: str, observation: StabilityObservation) -> StabilityAssessment:
        self._validate(observation)
        prior = self._history[-1] if self._history else None
        delta = abs(observation.volatility - prior.volatility) if prior else 0.0
        predicted = min(1.0, round(0.65 * observation.volatility + 0.20 * observation.risk + 0.15 * delta, 8))
        forbidden = 1.0 if observation.forbidden_state else min(1.0, round(0.55 * observation.risk + 0.35 * predicted + 0.10 * observation.anomaly_signal, 8))
        anomaly = observation.anomaly_signal >= .70 or delta >= .45
        resilience = max(0.0, round(1.0 - (.45 * observation.risk + .35 * predicted + .20 * observation.anomaly_signal), 8))
        accepted = not observation.forbidden_state and forbidden < .80 and not (anomaly and observation.risk >= .70)
        posture = "PROHIBITED" if observation.forbidden_state else "GUARDED" if not accepted else "STABLE" if resilience >= .60 else "CAUTIOUS"
        policy = "REJECT" if not accepted else "STABILISE" if posture == "CAUTIOUS" else "OBSERVE"
        world = self.layer.runtime.load_world(world_id)
        event = self.layer.runtime._chronicle(world, "mining_stability_reasoning", FoldOutcome.ACCEPTED.value if accepted else FoldOutcome.REJECTED.value, {"observation": asdict(observation), "posture": posture, "predicted_volatility": predicted, "forbidden_state_likelihood": forbidden, "anomaly_detected": anomaly, "resilience_score": resilience, "policy_proposal": policy})
        self._history.append(observation)
        return StabilityAssessment(observation.observation_id, posture, predicted, forbidden, anomaly, resilience, policy, accepted, event.event_hash, "Abstract, deterministic laboratory reasoning only; not a prediction of mining performance, share acceptance, revenue, profitability, or live operational outcome.")

    @staticmethod
    def _validate(o: StabilityObservation) -> None:
        if not o.observation_id.strip(): raise ValueError("observation identity required")
        if any(not 0.0 <= float(v) <= 1.0 for v in (o.risk,o.volatility,o.anomaly_signal)): raise ValueError("risk, volatility, and anomaly signal must be bounded in [0,1]")
        if any(not label.strip() for label in o.agent_labels): raise ValueError("agent labels must be descriptive non-empty labels")

__all__=["StabilityObservation","StabilityAssessment","StabilityReasoningModule"]
