"""Explicit operator-delegated execution/rollback stand-ins for EUCLID frontier.

These ports invoke real host adapters. They are NEVER selected automatically,
never issue authority or attest qualification, and are NOT production isolation.
The frontier loop continues to own permissions, budgets, verification and kill.
A deployment must replace these cooperative ports with its external enforcement
before claiming hard time/memory limits, isolation or production qualification.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from types import MappingProxyType


class OperatorDevelopmentGuards:
    """Permissive execution within exact, explicitly delegated host request scopes.

    Build outside the operational actor with the operator's adapter/request
    allowlist and durable AL HARAS audit. Pass ``execute`` and ``rollback`` as
    FrontierAgent's existing callback ports. No parallel dispatcher or learner.
    Revocation stops new executions but permits budgeted recovery of prior work.
    """
    profile = "operator-development"
    assurance = "OPERATOR_AUTHORIZED_STANDIN"
    process_isolated = False
    independently_qualified = False
    runtime_enforcement = "cooperative-and-post-return"

    def __init__(self, *, profile, delegated_by, approved, audit, clock):
        from al_haras import HashChainAudit
        from chronus.agent.permissions import ActionRequest
        if profile != self.profile or type(delegated_by) is not str or not delegated_by.strip():
            raise ValueError("explicit operator-development profile and delegating operator required")
        if type(approved) is not tuple or not approved or not callable(clock):
            raise TypeError("nonempty tuple of host (adapter, ActionRequest) bindings and clock required")
        if not isinstance(audit, HashChainAudit):
            raise TypeError("durable AL HARAS audit required")
        bindings={}
        for pair in approved:
            if type(pair) is not tuple or len(pair) != 2 or type(pair[1]) is not ActionRequest:
                raise TypeError("actual adapter and typed exact request required")
            adapter, request=pair
            if not callable(getattr(adapter,"execute",None)) or not callable(getattr(adapter,"rollback",None)):
                raise TypeError("actual execute and rollback adapter ports required")
            digest=self._digest(request)
            if digest in bindings:
                raise ValueError("duplicate delegated request")
            bindings[digest]=(adapter,request)
        self.bindings=MappingProxyType(bindings)
        self.delegated_by,self.audit,self.clock=delegated_by,audit,clock
        self._revoked=False
        self.audit.append({"kind":"operator-standin-configured","operator":delegated_by,
            "profile":self.profile,"assurance":self.assurance,"scopes":sorted(bindings),
            "process_isolated":False,"independently_qualified":False})

    @staticmethod
    def _digest(request):
        # Enum values are the native contract's exact string representation.
        return hashlib.sha256(json.dumps(asdict(request),sort_keys=True,separators=(",",":"),
            default=lambda v:v.value,allow_nan=False).encode()).hexdigest()

    def revoke(self):
        # Revocation becomes effective even if the audit disk subsequently fails.
        self._revoked=True
        self.audit.append({"kind":"operator-standin-revoked","operator":self.delegated_by})

    def _admit(self, adapter, request, deadline_ns, hard_limits, *, recovery):
        from chronus.agent.permissions import ActionRequest
        if type(request) is not ActionRequest:
            raise PermissionError("typed delegated request required")
        digest=self._digest(request); binding=self.bindings.get(digest)
        if binding is None or binding[0] is not adapter or binding[1] != request:
            raise PermissionError("adapter/request not explicitly delegated by operator")
        if self._revoked and not recovery:
            raise PermissionError("operator delegation revoked")
        now=self.clock()
        if type(now) is not int or type(deadline_ns) is not int or now >= deadline_ns:
            raise TimeoutError("execution deadline unavailable or expired")
        if (type(hard_limits) is not dict or not hard_limits
                or any(type(k) is not str or type(v) is not int or v < 0 for k,v in hard_limits.items())):
            raise ValueError("explicit nonnegative integer resource envelope required")
        self.audit.append({"kind":"operator-recovery-admitted" if recovery else "operator-execution-admitted",
            "scope_digest":digest,"operator":self.delegated_by,"deadline_ns":deadline_ns,
            "limits":dict(hard_limits),"assurance":self.assurance})
        return digest

    def execute(self, adapter, request, *, deadline_ns, hard_limits, permission_scope):
        from chronus.agent.control import ExecutionReceipt
        if permission_scope != request:
            raise PermissionError("request differs from admitted permission scope")
        digest=self._admit(adapter,request,deadline_ns,hard_limits,recovery=False)
        limits=dict(hard_limits)
        try:
            receipt=adapter.execute(request,deadline_ns=deadline_ns)
            if type(receipt) is not ExecutionReceipt:
                raise TypeError("real typed adapter ExecutionReceipt required")
            actual=dict(receipt.actual_costs)
            if set(actual) != set(limits) or any(actual[k]>limits[k] for k in actual):
                raise RuntimeError("adapter reported resource envelope exceeded")
            if self.clock() >= deadline_ns:
                raise TimeoutError("adapter returned after deadline; effects may require rollback")
            self.audit.append({"kind":"operator-execution-returned","scope_digest":digest,
                "output_evidence":receipt.output_evidence,"actual_costs":actual,"qualified":False})
            return receipt
        except Exception as exc:
            self._failed(digest,exc,recovery=False)
            raise

    def rollback(self, adapter, checkpoint, *, deadline_ns, hard_limits, permission_scope):
        digest=self._admit(adapter,permission_scope,deadline_ns,hard_limits,recovery=True)
        try:
            result=adapter.rollback(checkpoint)
            if self.clock() >= deadline_ns:
                raise TimeoutError("rollback returned after deadline; restored state not established")
            self.audit.append({"kind":"operator-recovery-returned","scope_digest":digest,
                "restoration_verified":False})
            # The existing frontier loop must observe and verify restoration.
            return result
        except Exception as exc:
            self._failed(digest,exc,recovery=True)
            raise

    def _failed(self,digest,exc,*,recovery):
        try:
            self.audit.append({"kind":"operator-recovery-failed" if recovery else "operator-execution-failed",
                "scope_digest":digest,"error_type":type(exc).__name__})
        except Exception as audit_exc:
            exc.add_note("failure audit unavailable: "+type(audit_exc).__name__)
