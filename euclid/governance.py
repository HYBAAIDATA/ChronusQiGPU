"""Governed organ registry, delegation gates and task orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .contracts import Authority, Capability, Health
from .evidence import EvidenceChain


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    gates: Mapping[str, bool]
    reason: str


@dataclass
class Organ:
    organ_id: str
    capabilities: frozenset[str]
    authority: Authority
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    health: Health = Health.HEALTHY


class OrganRegistry:
    def __init__(self) -> None:
        self._organs: dict[str, Organ] = {}

    def register(self, organ: Organ) -> None:
        if not organ.organ_id or not organ.capabilities:
            raise ValueError("organ identity and capabilities are required")
        if organ.organ_id in self._organs:
            raise ValueError("duplicate organ")
        self._organs[organ.organ_id] = organ

    def get(self, organ_id: str) -> Organ:
        try:
            return self._organs[organ_id]
        except KeyError as exc:
            raise ValueError("unknown organ") from exc

    def report(self) -> list[dict[str, Any]]:
        return [
            {
                "organ_id": organ.organ_id,
                "capabilities": sorted(organ.capabilities),
                "authority": organ.authority.value,
                "health": organ.health.value,
            }
            for organ in sorted(self._organs.values(), key=lambda item: item.organ_id)
        ]


class Delegator:
    DISPATCH_GATES = ("capable", "healthy", "permitted", "confident", "safe")
    INTEGRATION_GATES = ("coherent", "truth_evidence", "causal", "feedback")

    def __init__(self, registry: OrganRegistry, evidence: EvidenceChain) -> None:
        self.registry = registry
        self.evidence = evidence

    def dispatch(
        self,
        organ_id: str,
        capability: str,
        request: Mapping[str, Any],
        *,
        permitted: bool,
        confident: bool,
        safe: bool,
    ) -> Mapping[str, Any]:
        organ = self.registry.get(organ_id)
        gates = {
            "capable": capability in organ.capabilities,
            "healthy": organ.health is Health.HEALTHY,
            "permitted": bool(permitted),
            "confident": bool(confident),
            "safe": bool(safe),
        }
        if not all(gates.values()):
            self.evidence.append("delegation-veto", {"organ": organ_id, "gates": gates})
            raise PermissionError("delegation gates rejected request")
        result = dict(organ.handler(dict(request)))
        self.evidence.append(
            "delegation-result",
            {"organ": organ_id, "capability": capability, "request": dict(request),
             "result": result},
        )
        return result

    def approve_integration(
        self, *, coherent: bool, truth_evidence: bool, causal: bool, feedback: bool
    ) -> GateDecision:
        gates = {
            "coherent": bool(coherent),
            "truth_evidence": bool(truth_evidence),
            "causal": bool(causal),
            "feedback": bool(feedback),
        }
        accepted = all(gates.values())
        reason = "all integration gates passed" if accepted else "integration veto"
        self.evidence.append("integration-decision", {"accepted": accepted, "gates": gates})
        return GateDecision(accepted, gates, reason)
