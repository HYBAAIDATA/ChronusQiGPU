"""Independent, custodied mining recovery proof; no actuator or replacement store.

A producer status is retained as an observation, never accepted as verification.
The verifier reads separate authorisation, execution and postcondition bindings
from the *existing* shared THESEUS/OVID fabric. Missing bindings fail closed.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class EvidenceClass(StrEnum):
    OBSERVED = "OBSERVED"
    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    PREDICTED = "PREDICTED"
    SIMULATED = "SIMULATED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class RuntimeObservation:
    observation_id: str
    subject: str
    tenant: str
    source_subsystem: str
    metric: str
    observed_value: Any
    expected_range: Any
    timestamp_ns: int
    evidence_class: EvidenceClass
    provenance: str
    source_commit: str
    correlation_id: str

    def __post_init__(self) -> None:
        identities = (
            self.observation_id, self.subject, self.tenant, self.source_subsystem,
            self.metric, self.provenance, self.correlation_id,
        )
        if not all(isinstance(x, str) and x for x in identities):
            raise ValueError("observation identities and provenance are required")
        if type(self.timestamp_ns) is not int or self.timestamp_ns <= 0:
            raise ValueError("positive source timestamp required")
        if not isinstance(self.evidence_class, EvidenceClass):
            raise ValueError("typed evidence class required")
        if self.evidence_class is EvidenceClass.UNAVAILABLE:
            if self.observed_value is not None:
                raise ValueError("unavailable telemetry is not zero")
        elif self.observed_value is None:
            raise ValueError("available observation requires a value")
        if isinstance(self.observed_value, float) and not math.isfinite(self.observed_value):
            raise ValueError("non-finite telemetry")

    def production_eligible(self, *, now_ns: int, max_age_ns: int) -> bool:
        if type(max_age_ns) is not int or max_age_ns <= 0:
            raise ValueError("explicit positive freshness contract required")
        try:
            commit_valid = len(self.source_commit) == 40 and len(bytes.fromhex(self.source_commit)) == 20
        except ValueError:
            commit_valid = False
        return (
            self.evidence_class in {EvidenceClass.OBSERVED, EvidenceClass.MEASURED}
            and commit_valid
            and 0 <= now_ns - self.timestamp_ns <= max_age_ns
        )

    def matches_contract(self) -> bool:
        contract = self.expected_range
        if not isinstance(contract, Mapping) or not contract.get("contract_ref"):
            return False
        if contract.get("operator") == "eq":
            expected = contract.get("value")
            return type(expected) is type(self.observed_value) and self.observed_value == expected
        if contract.get("operator") == "range":
            low, high, value = contract.get("min"), contract.get("max"), self.observed_value
            values = (low, high, value)
            return (
                all(type(x) in (int, float) and math.isfinite(x) for x in values)
                and low <= value <= high
            )
        return False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutcomeVerification:
    verified: bool
    claim_class: str
    reason: str
    proof_binding_id: str | None = None
    causal_claim: str = "UNAVAILABLE"


class CustodiedMiningOutcomeVerifier:
    """Read-only verifier over a supplied canonical SystemDataPort.

    No root, key, file, SQL connection or alternate custody is constructed here.
    A bounded freshness interval is supplied explicitly by deployment policy.
    Producers must publish the schemas below before a recovery can be certified.
    This verifier does not fabricate those missing producer integrations.
    """

    def __init__(self, port: Any, *, tenant: str, source_commit: str, max_age_ns: int) -> None:
        if (not tenant or len(source_commit) != 40
                or type(max_age_ns) is not int or max_age_ns <= 0):
            raise ValueError("tenant, pinned source commit and freshness contract required")
        self.port = port
        self.tenant = tenant
        self.source_commit = source_commit
        self.max_age_ns = max_age_ns

    def _read(self, binding_id: str, *, source: str) -> Mapping[str, Any]:
        if not isinstance(binding_id, str) or not binding_id:
            raise ValueError("missing independent binding")
        verdict = self.port.fabric.verify(binding_id)
        if verdict.get("passed") is not True:
            raise ValueError("custody verification failed")
        bindings = self.port.fabric.graph()["bindings"]
        binding = next((b for b in bindings if b["binding_id"] == binding_id), None)
        if binding is None or binding.get("source_system") != source:
            raise ValueError("wrong domain authority")
        body = json.loads(self.port.read(binding_id).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("proof must be a JSON object")
        if body.get("tenant") != self.tenant or body.get("source_commit") != self.source_commit:
            raise ValueError("tenant or source revision mismatch")
        return body

    def verify(self, recovery: Mapping[str, Any], *, now_ns: int) -> OutcomeVerification:
        proof_id = recovery.get("proof_binding_id")
        if not proof_id:
            return OutcomeVerification(False, "UNAVAILABLE", "independent proof not published")
        try:
            proof = self._read(proof_id, source="pythia")
            if proof.get("schema") != "salamander.mining-outcome-proof/v1":
                raise ValueError("unsupported proof schema")
            recovery_id = recovery.get("recovery_id")
            if not recovery_id or proof.get("recovery_id") != recovery_id:
                raise ValueError("wrong recovery identity")
            if recovery.get("state") != "VERIFIED":
                raise ValueError("producer outcome contradicts recovery proof")
            for key in ("tenant", "subject", "action_id", "action", "resource", "correlation_id"):
                if not recovery.get(key) or recovery[key] != proof.get(key):
                    raise ValueError("recovery/proof identity mismatch")
            authorization = self._read(proof.get("authorization_ref"), source="al_haras")
            execution = self._read(proof.get("execution_ref"), source="chronus")
            postcondition = self._read(proof.get("postcondition_ref"), source="pythia")
            if len({proof_id, proof.get("authorization_ref"), proof.get("execution_ref"),
                    proof.get("postcondition_ref")}) != 4:
                raise ValueError("evidence identities are not independent")
            for doc, schema in (
                (authorization, "salamander.action-authorization/v1"),
                (execution, "salamander.owned-action-execution/v1"),
                (postcondition, "salamander.independent-postcondition/v1"),
            ):
                if doc.get("schema") != schema or doc.get("recovery_id") != recovery_id:
                    raise ValueError("unbound evidence")
                for key in ("subject", "action_id", "action", "resource", "correlation_id"):
                    if not proof.get(key) or doc.get(key) != proof[key]:
                        raise ValueError("action/evidence identity mismatch")
            if authorization.get("decision") != "ALLOW" or not authorization.get("policy_version"):
                raise ValueError("AL HARAS did not authorise this action")
            if not authorization.get("actor") or not authorization.get("risk"):
                raise ValueError("actor/risk binding unavailable")
            authorized_ns = authorization.get("timestamp_ns")
            started_ns = execution.get("started_ns")
            completed_ns = execution.get("completed_ns")
            expiry_ns = authorization.get("expires_ns")
            if not all(type(x) is int for x in (authorized_ns, started_ns, completed_ns, expiry_ns)):
                raise ValueError("action timing unavailable")
            if not authorized_ns <= started_ns <= completed_ns <= expiry_ns:
                raise ValueError("expired or post-hoc authorisation")
            if execution.get("executed") is not True or execution.get("evidence_class") != "OBSERVED":
                raise ValueError("execution not observed")
            if postcondition.get("verified") is not True or not postcondition.get("verifier_id"):
                raise ValueError("postcondition rejected")
            if postcondition.get("verifier_id") == execution.get("actuator_id"):
                raise ValueError("actuator cannot verify itself")
            observations = postcondition.get("observations")
            if not isinstance(observations, list) or not observations:
                raise ValueError("fresh postcondition observations missing")
            for raw in observations:
                raw = dict(raw)
                raw["evidence_class"] = EvidenceClass(raw["evidence_class"])
                obs = RuntimeObservation(**raw)
                if not obs.production_eligible(now_ns=now_ns, max_age_ns=self.max_age_ns):
                    raise ValueError("non-production or stale observation")
                if not obs.matches_contract():
                    raise ValueError("independent observation violates postcondition contract")
                contract_ref = obs.expected_range["contract_ref"]
                contract = self._read(contract_ref, source="pythia")
                expected_range = {k: v for k, v in obs.expected_range.items() if k != "contract_ref"}
                if (contract.get("schema") != "salamander.postcondition-contract/v1"
                        or contract.get("subject") != obs.subject
                        or contract.get("metric") != obs.metric
                        or contract.get("expected_range") != expected_range):
                    raise ValueError("postcondition threshold differs from custodied contract")
                if (obs.tenant != self.tenant or obs.subject != proof["subject"]
                        or obs.source_commit != self.source_commit
                        or obs.correlation_id != proof["correlation_id"]
                        or obs.source_subsystem != "pythia"
                        or obs.timestamp_ns <= completed_ns):
                    raise ValueError("postcondition observation not bound/fresh")
            if not execution.get("actuator_id"):
                raise ValueError("owning actuator identity missing")
            if postcondition.get("expected_vs_observed") is None:
                raise ValueError("postcondition comparison missing")
            return OutcomeVerification(True, "VERIFIED", "independent postcondition verified", proof_id)
        except Exception as exc:
            # Do not expose raw producer payloads or secrets in diagnostics.
            return OutcomeVerification(False, "UNAVAILABLE", type(exc).__name__, proof_id)


READINESS_GATES = (
    "observation_gate", "diagnosis_gate", "authorization_gate", "actuation_gate",
    "independent_verification_gate", "rollback_gate", "evidence_gate",
    "persistence_gate", "restart_replay_gate", "adversarial_gate", "mutation_gate",
    "production_composition_gate",
)


def unqualified_readiness() -> Mapping[str, Any]:
    """Current bridge lacks the full production voyages; it cannot self-certify.

    Gate receipts must eventually be independently resolved at composition, not
    supplied as booleans by an endpoint or inferred from local contract tests.
    """
    gates = {gate: "UNAVAILABLE" for gate in READINESS_GATES}
    return {
        "gates": gates,
        "production_ready": all(value == "VERIFIED" for value in gates.values()),
        "verdict": "NOT_PRODUCTION_READY",
        "reason": "complete source-bound production qualification receipts unavailable",
    }
