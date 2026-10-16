"""Explicit canonical EUCLID -> PHILOS qualification-owner integration.

Requires the canonical runtime security/dispatch revision in PR74. Host-approved
cases and external authorization are mandatory. No provider, signer, grant,
qualification, learner or alternative runtime is created by binding.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

from .models.candidate import EmergentCandidate
from .models.qualification import QualifiedEmergent, RejectedQualification, SuspendedQualification
from .substrate.executors import BaseExecutor
from .trusted_core.access_control import GovernanceToken, InvalidGovernanceTokenError
from .trusted_core.custody import CandidateSnapshot
from .trusted_core.qualification_service import EmergentQualificationService


@dataclass(frozen=True)
class QualificationCase:
    """Host-approved immutable candidate snapshot and explicit executor bindings.

    An absent pre-recorded window requests telemetry from this invocation's signed
    measured runs. A supplied window must match those runs exactly; arbitrary
    historical telemetry cannot certify a new execution.

    Executor implementations remain trusted host references. This is not OS
    isolation, initial detection attestation or a measured-evidence credential.
    """
    candidate: CandidateSnapshot
    executor_A: BaseExecutor
    executor_B: BaseExecutor
    observation_window: tuple = ()

    def __post_init__(self):
        if (type(self.candidate) is not CandidateSnapshot
                or not isinstance(self.executor_A, BaseExecutor)
                or not isinstance(self.executor_B, BaseExecutor)
                or type(self.observation_window) is not tuple):
            raise TypeError("frozen candidate, real executor owners and tuple window required")
        self.candidate.verify(self.candidate.materialize())

    @classmethod
    def capture(cls, candidate: EmergentCandidate, executor_A: BaseExecutor,
                executor_B: BaseExecutor, *, observation_window=()):
        return cls(CandidateSnapshot.capture(candidate), executor_A, executor_B,
                   tuple(copy.deepcopy(observation_window)))


class PhilosSpecialist:
    """Qualification owner adapter; never installed as a read-only fabric handler."""
    def __init__(self, service, cases, audit):
        if not isinstance(service, EmergentQualificationService) or service.authorization is None:
            raise TypeError("real EQS with explicit public-key authorization required")
        if not isinstance(cases, Mapping) or not cases:
            raise ValueError("host-approved qualification cases required")
        approved = {}
        for name, case in cases.items():
            if type(name) is not str or not name or len(name) > 128 or type(case) is not QualificationCase:
                raise TypeError("bounded case identifiers and QualificationCase bindings required")
            # Detach the window again; retain the existing executor owners.
            approved[name] = QualificationCase(case.candidate, case.executor_A, case.executor_B,
                                               tuple(copy.deepcopy(case.observation_window)))
        self.service, self.cases, self.audit = service, MappingProxyType(approved), audit

    def handle(self, request):
        from Intelligence.capability_fabric import snapshot_json
        request = snapshot_json(request)
        if (type(request) is not dict or set(request) != {"operation", "case_id", "governance_token"}
                or request["operation"] != "qualify" or type(request["case_id"]) is not str):
            raise ValueError("exact qualify/case_id/governance_token request required")
        case = self.cases.get(request["case_id"])
        if case is None:
            raise PermissionError("qualification case not approved by host")
        if type(request["governance_token"]) is not dict:
            raise InvalidGovernanceTokenError("serialized scoped governance token required")
        token = GovernanceToken(**request["governance_token"])
        fingerprint = case.candidate.fingerprint
        request_digest = hashlib.sha256(json.dumps(request,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        self.audit.append({"kind": "philos-request-admitted", "request_digest": request_digest,
                           "case_id": request["case_id"], "candidate_fingerprint": fingerprint})
        try:
            outcome = self.service.qualify(case.candidate.materialize(),case.executor_A,case.executor_B,
                governance_token=token,post_qualification_window=(
                    copy.deepcopy(case.observation_window) if case.observation_window else None))
            if type(outcome) not in (QualifiedEmergent, RejectedQualification, SuspendedQualification):
                raise TypeError("unknown native qualification outcome")
            result = {"status": outcome.status.value, "qualified": type(outcome) is QualifiedEmergent,
                      "qualification_invoked": True, "independently_qualified": False,
                      "candidate_fingerprint": fingerprint, "outcome": outcome.to_dict()}
            self.audit.append({"kind":"philos-request-completed","request_digest":request_digest,
                               "candidate_fingerprint":fingerprint,"status":result["status"],
                               "result_digest":hashlib.sha256(json.dumps(result,sort_keys=True,
                                   separators=(",", ":"),allow_nan=False).encode()).hexdigest()})
            return result
        except Exception as exc:
            try:
                self.audit.append({"kind":"philos-request-failed","request_digest":request_digest,
                                   "candidate_fingerprint":fingerprint,"error_type":type(exc).__name__})
            except Exception as audit_exc:
                exc.add_note("PHILOS failure audit unavailable: "+type(audit_exc).__name__)
            raise


def bind_philos(runtime, service, *, cases, organ_id="philos"):
    """Bind the real qualification owner, not an executor's self-promotion path.

    Requires PR74's canonical runtime revision and a configured Guardian. Caller
    must independently obtain AL HARAS entitlement, creator-scoped dispatch
    rights and a one-use candidate-bound token from an external trusted officer.
    """
    from euclid.runtime import EuclidRuntime
    import inspect
    if (not isinstance(runtime, EuclidRuntime) or not callable(getattr(runtime,"bind_intelligence",None))
            or "authority" not in inspect.signature(runtime.register_specialist).parameters):
        raise RuntimeError("canonical EUCLID security/dispatch integration revision required (PR74)")
    if runtime._closed or runtime.guardian is None:
        raise RuntimeError("open canonical runtime and explicit AL HARAS Guardian required")
    if type(organ_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}",organ_id) is None:
        raise ValueError("bounded path-free organ identifier required")
    from al_haras import HashChainAudit
    audit = HashChainAudit(runtime.state_dir/"philos"/(organ_id+".jsonl"))
    specialist = PhilosSpecialist(service,cases,audit)
    from euclid.contracts import Authority
    runtime.register_specialist(organ_id,specialist,operations=("qualify",),authority=Authority.PROPOSE)
    runtime.evidence.append("philos-owner-bound",{"organ":organ_id,"cases":sorted(specialist.cases),
                            "rights_granted":False,"signing_authority_installed":False})
    return specialist
