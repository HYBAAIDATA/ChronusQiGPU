"""Route markers and fail-closed Guardian preflight/evidence helpers."""
from __future__ import annotations
from dataclasses import dataclass
from functools import wraps
from typing import Any,Callable,Mapping
@dataclass(frozen=True)
class MediationDecision:allowed:bool;status_code:int;receipt:dict[str,Any]
class MediationIncomplete(RuntimeError):pass
def guardian_middleware(fn):
 fn.__guardian_mediated__=True;return fn
def evidence_attach(fn):
 fn.__guardian_evidence__=True;return fn
def privileged_exempt(justification:str):
 if not justification.strip():raise ValueError("exemption justification required")
 def mark(fn):fn.__privileged_exempt__=justification;return fn
 return mark
def privileged_route(router,method:str,path:str,**route_kwargs):
 """Register a route with both mandatory mediation markers.

 Framework adapters should expose this helper rather than the raw router for
 new privileged endpoints; the static audit still verifies the final tree.
 """
 def register(fn):
  wrapped=guardian_middleware(evidence_attach(fn))
  return getattr(router,method)(path,**route_kwargs)(wrapped)
 return register
def evaluate_guardian(api,headers:Mapping[str,str],operation:str,resource:str,payload:dict|None=None)->MediationDecision:
 code,receipt=api.evaluate(headers=dict(headers),body={"operation":operation,"resource":resource,"payload":payload or {}})
 return MediationDecision(code==200,code,receipt)
def attach_receipt(payload:Any,receipt:dict)->dict:
 body=dict(payload) if isinstance(payload,dict) else {"result":payload}
 body["guardian_receipt"]=receipt;return body
