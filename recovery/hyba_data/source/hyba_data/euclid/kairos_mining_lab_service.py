"""Sealed Kairos Mining-Orchestration Lab Service.

Versioned in-process service contract for deterministic laboratory experiments.
No listener, pool, wallet, miner, credential, provider, or public API exists.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .kairos_execution import KairosExecutionLayer, OperatorAction

API_VERSION = "v1"
SERVICE_MODE = "SEALED_LABORATORY"


@dataclass(frozen=True)
class LabServicePolicy:
    allowed_operators: tuple[str, ...] = ("andre",)
    api_version: str = API_VERSION
    service_mode: str = SERVICE_MODE
    network_enabled: bool = False
    external_identity_enabled: bool = False
    external_providers_enabled: bool = False
    multi_user_enabled: bool = False
    live_mining_enabled: bool = False

    def __post_init__(self) -> None:
        if (self.api_version != API_VERSION or self.service_mode != SERVICE_MODE or self.network_enabled
                or self.external_identity_enabled or self.external_providers_enabled
                or self.multi_user_enabled or self.live_mining_enabled):
            raise ValueError("Kairos Mining Lab Service is sealed and laboratory-only")
        if not self.allowed_operators or any(not item.strip() for item in self.allowed_operators):
            raise ValueError("at least one named laboratory operator required")


@dataclass(frozen=True)
class MiningExperimentRequest:
    experiment_id: str
    operator_id: str
    world_id: str
    domain_from: str
    domain_to: str
    intent: str
    risk: float
    volatility: float
    agent_labels: tuple[str, ...]
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]
    performance_claim: str | None = None


@dataclass(frozen=True)
class EvidenceGateResult:
    passed: bool
    reasons: tuple[str, ...]
    evidence_class: str


@dataclass(frozen=True)
class MiningExperimentResult:
    experiment_id: str
    outcome: str
    evidence_gate: EvidenceGateResult
    world_hash: str
    chronicle_head: str | None
    risk: float
    volatility: float
    resonance_triggered: bool
    claim_boundary: str


class MiningEvidenceGate:
    FORBIDDEN_KEYS = frozenset({"wallet", "wallet_address", "private_key", "seed_phrase", "pool", "pool_url", "stratum", "endpoint", "credential", "api_key", "token", "hashrate", "revenue", "profit", "accepted_share"})

    def evaluate(self, request: MiningExperimentRequest, policy: LabServicePolicy) -> EvidenceGateResult:
        reasons: list[str] = []
        if request.operator_id not in policy.allowed_operators:
            reasons.append("operator is outside the sealed laboratory allowlist")
        if not request.experiment_id.strip() or not request.world_id.strip():
            reasons.append("experiment and world identity required")
        if not 0.0 <= float(request.risk) <= 1.0 or not 0.0 <= float(request.volatility) <= 1.0:
            reasons.append("risk and volatility must be bounded in [0,1]")
        if request.performance_claim:
            reasons.append("performance claims are forbidden in laboratory experiments")
        present = self.FORBIDDEN_KEYS & {str(key).lower() for key in request.payload}
        if present:
            reasons.append("live-operation or credential field prohibited: " + ", ".join(sorted(present)))
        if any(not label.strip() for label in request.agent_labels):
            reasons.append("agent labels must be non-empty")
        return EvidenceGateResult(not reasons, tuple(reasons), "LABORATORY_EXPERIMENT_ONLY")


class KairosMiningLabService:
    """Narrow API contract only; no network transport is bound."""

    def __init__(self, layer: KairosExecutionLayer | None = None, policy: LabServicePolicy | None = None) -> None:
        self.layer = layer or KairosExecutionLayer()
        self.policy = policy or LabServicePolicy()
        self.gate = MiningEvidenceGate()
        self.audit: list[Mapping[str, Any]] = []
        self._enforce_boundary()

    def routes(self) -> Mapping[str, str]:
        return {"GET /v1/health": "sealed service posture", "POST /v1/worlds": "create laboratory world", "POST /v1/experiments": "execute evidence-gated mining-orchestration experiment", "GET /v1/worlds/{world_id}": "read in-process world state"}

    def health(self, operator_id: str) -> Mapping[str, Any]:
        self._authorise(operator_id)
        self._enforce_boundary()
        return {"api_version": API_VERSION, "service_mode": SERVICE_MODE, "healthy": True, "network_listener": False, "external_identity": False, "live_mining": False, "performance_claims": False}

    def create_world(self, operator_id: str, world_id: str, snapshot_hash: str) -> Mapping[str, Any]:
        self._authorise(operator_id)
        self._enforce_boundary()
        world = self.layer.runtime.create_world(world_id, snapshot_hash)
        self.layer.runtime.bootstrap_world(world.world_id)
        session = self.layer.runtime.activate_session(self.layer.runtime.open_session(operator_id).session_id)
        response = {"world_id": world.world_id, "session_id": session.session_id, "world_hash": world.state_hash, "api_version": API_VERSION}
        self.audit.append({"kind": "world_created", **response})
        return response

    def execute_experiment(self, session_id: str, request: MiningExperimentRequest) -> MiningExperimentResult:
        self._enforce_boundary()
        gate = self.gate.evaluate(request, self.policy)
        if not gate.passed:
            result = MiningExperimentResult(request.experiment_id, "REJECTED", gate, "", None, float(request.risk), float(request.volatility), False, "Laboratory request rejected before world mutation.")
            self.audit.append({"kind": "experiment_rejected", "request": asdict(request), "result": asdict(result)})
            return result
        action = OperatorAction(request.domain_from, request.domain_to, request.intent, {**dict(request.payload), "mining_experiment": request.experiment_id, "risk": float(request.risk), "agent_labels": request.agent_labels}, {"risk": float(request.risk), "volatility": float(request.volatility)}, {**dict(request.provenance), "evidence_class": gate.evidence_class})
        execution = self.layer.execute(request.world_id, session_id, action)
        state = self.layer.world_state(request.world_id)
        result = MiningExperimentResult(request.experiment_id, execution.outcome.value, gate, state["world_hash"], state["chronicle_head"], float(request.risk), float(request.volatility), execution.resonance_triggered, "Deterministic in-process mining-orchestration experiment only; no live mining, pool, wallet, network, performance, revenue, or profitability claim.")
        self.audit.append({"kind": "experiment_executed", "request": asdict(request), "result": asdict(result)})
        return result

    def world_state(self, operator_id: str, world_id: str) -> Mapping[str, Any]:
        self._authorise(operator_id)
        self._enforce_boundary()
        return self.layer.world_state(world_id)

    def _authorise(self, operator_id: str) -> None:
        if operator_id not in self.policy.allowed_operators:
            raise PermissionError("sealed laboratory caller not authorised")

    def _enforce_boundary(self) -> None:
        p, b = self.policy, self.layer.runtime.boundary
        if (p.network_enabled or p.external_identity_enabled or p.external_providers_enabled or p.multi_user_enabled or p.live_mining_enabled
                or b.network_enabled or b.multi_user_enabled or b.external_providers_enabled):
            raise RuntimeError("sealed laboratory boundary violation")


__all__ = ["API_VERSION", "SERVICE_MODE", "LabServicePolicy", "MiningExperimentRequest", "EvidenceGateResult", "MiningExperimentResult", "MiningEvidenceGate", "KairosMiningLabService"]
