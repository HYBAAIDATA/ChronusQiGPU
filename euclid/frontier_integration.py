"""Canonical EUCLID dispatch into its actual frontier-agent constituent.

Host-approved plans only; no caller-supplied executable plan, signer, policy or
permission. Owner loop retains all authority, resource and verification checks.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
import re
import sqlite3
from types import MappingProxyType


@dataclass(frozen=True)
class FrontierCase:
    objective: object
    cognition: object
    plan: object

    def __post_init__(self):
        from chronus.agent.goal import Objective
        from chronus.agent.cognition import CognitiveState
        from chronus.agent.control import Plan
        if type(self.objective) is not Objective or type(self.cognition) is not CognitiveState or type(self.plan) is not Plan:
            raise TypeError("native frontier objective, cognition and plan required")
        if (self.plan.objective_id != self.objective.id
                or self.plan.cognition_digest != self.cognition.fingerprint):
            raise ValueError("host frontier case bindings differ")


class FrontierSpecialist:
    def __init__(self,agent,cases,audit,replay_path):
        from chronus.agent.main import FrontierAgent
        from chronus.agent._contracts import digest
        if not isinstance(agent,FrontierAgent) or not cases:
            raise TypeError("actual FrontierAgent and approved host cases required")
        self.agent,self.audit,self.replay_path=agent,audit,replay_path
        approved={}
        for name,case in cases.items():
            if type(name) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}",name) is None or type(case) is not FrontierCase:
                raise TypeError("bounded named native FrontierCase required")
            detached=copy.deepcopy(case)
            # Bind all case values, not just capability/objective names.
            approved[name]=(detached,digest(detached))
        self.cases=MappingProxyType(approved)
        self._db(lambda db:db.execute("CREATE TABLE IF NOT EXISTS used_cases (case_id TEXT PRIMARY KEY, case_digest TEXT NOT NULL)"))

    def _db(self,operation):
        db=sqlite3.connect(self.replay_path,timeout=2)
        try:
            with db:return operation(db)
        finally:db.close()

    def handle(self,request):
        from chronus.agent._contracts import digest,wire
        from chronus.agent.control import Outcome,StoppingCondition
        from Intelligence.capability_fabric import snapshot_json
        request=snapshot_json(request)
        if type(request) is not dict or set(request)!={"operation","case_id"} or request["operation"]!="run" or type(request["case_id"]) is not str:
            raise ValueError("exact run/case_id request required; plans are host-owned")
        if request["case_id"] not in self.cases:
            raise PermissionError("frontier case not host-approved")
        case,fingerprint=self.cases[request["case_id"]]
        case=copy.deepcopy(case)
        if digest(case)!=fingerprint:
            raise PermissionError("host frontier case mutated")
        self.audit.append({"kind":"frontier-request-admitted","case_id":request["case_id"],
                           "case_digest":fingerprint,"agent_id":self.agent.identity.id})
        try:
            # Single use persists across restart. Failure never refunds/retries a case.
            try:
                self._db(lambda db:db.execute("INSERT INTO used_cases VALUES (?, ?)",
                    (request["case_id"],fingerprint)))
            except sqlite3.IntegrityError as exc:
                raise PermissionError("frontier case already attempted; explicit new host approval required") from exc
            outcome=self.agent.run(case.objective,case.cognition,case.plan)
            if type(outcome) is not Outcome:
                raise TypeError("native frontier Outcome required")
            result={"status":outcome.stop.value,"goal_achieved":outcome.stop is StoppingCondition.GOAL_ACHIEVED,
                    "run_invoked":True,"independently_qualified":False,"case_digest":fingerprint,
                    "outcome":wire(outcome)}
            self.audit.append({"kind":"frontier-request-completed","case_id":request["case_id"],
                "case_digest":fingerprint,"status":result["status"],"result_digest":digest(result)})
            return result
        except Exception as exc:
            try:self.audit.append({"kind":"frontier-request-failed","case_digest":fingerprint,
                                   "error_type":type(exc).__name__})
            except Exception as audit_exc:exc.add_note("frontier failure audit unavailable: "+type(audit_exc).__name__)
            raise


def bind_frontier(runtime,agent,*,cases,organ_id="frontier"):
    """Bind a host-configured actual frontier owner without granting any rights.

    Requires the PR69 frontier owner implementation and PR74 canonical runtime.
    No authority signer, qualification service, execution guard or model is made.
    Host supplies real ports or explicitly selected operator-development stand-ins.
    """
    from euclid.runtime import EuclidRuntime
    from euclid.contracts import Authority
    from al_haras import HashChainAudit
    if not isinstance(runtime,EuclidRuntime) or runtime._closed or runtime.guardian is None:
        raise RuntimeError("open canonical runtime and explicit AL HARAS Guardian required")
    if type(organ_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}",organ_id) is None:
        raise ValueError("bounded path-free frontier organ identifier required")
    path=runtime.state_dir/"frontier";path.mkdir(parents=True,exist_ok=True)
    audit=HashChainAudit(path/(organ_id+".jsonl"))
    specialist=FrontierSpecialist(agent,cases,audit,path/(organ_id+".sqlite"))
    runtime.register_specialist(organ_id,specialist,operations=("run",),authority=Authority.MUTATE_WORLD)
    runtime.evidence.append("frontier-owner-bound",{"organ":organ_id,"cases":sorted(specialist.cases),
                           "rights_granted":False,"signing_authority_installed":False})
    return specialist
