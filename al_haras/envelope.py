"""Evidence-bound result envelope; operational metrics remain measured-only."""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from enum import Enum
import hashlib,hmac,json
from typing import Any,Callable
class FoldMode(str,Enum): PRESERVE="PRESERVE"; TRANSFORM="TRANSFORM"; REHYDRATE="REHYDRATE"; REJECT="REJECT"
@dataclass(frozen=True)
class ResultEnvelopeV2:
    payload:Any; object_id:str; tenant:str; instance:str; fold_family:str; fold_mode:FoldMode
    rehydration_count:int; residual:str|None; cassini_ok:bool; zeckendorf_ok:bool; chain_head:str
    witness_receipt_id:str; backend_certificate:str; backend_name:str; bytes_moved:int; proof_bytes:int
    latency_ms:str|None; energy_joules:str|None; verdict:dict[str,Any]
    signature_algorithm:str="HMAC-SHA256"; signature:str=""
    def unsigned(self)->dict[str,Any]:
        body=asdict(self);body["fold_mode"]=self.fold_mode.value;body["signature"]="";return body
    def canonical(self)->bytes:return json.dumps(self.unsigned(),sort_keys=True,separators=(",",":"),default=str).encode()

def _mode_consistent(mode:FoldMode,count:int)->bool:
    return count>=0 and ((mode is FoldMode.REHYDRATE and count>=1) or (mode is not FoldMode.REHYDRATE and count==0))

def build_envelope(*,signing_key:bytes,**values)->ResultEnvelopeV2:
    if len(signing_key)<32: raise ValueError("envelope key must be at least 32 bytes")
    env=ResultEnvelopeV2(**values)
    if not _mode_consistent(env.fold_mode,env.rehydration_count):
        raise ValueError("rehydration count is inconsistent with fold mode")
    sig=hmac.new(signing_key,env.canonical(),hashlib.sha256).hexdigest()
    return replace(env,signature=sig)

def verify_envelope(env:ResultEnvelopeV2,*,signing_key:bytes,verdict_verifier:Callable[[dict[str,Any]],bool],witness_verifier:Callable[[str,str],bool],backend_verifier:Callable[[str,str],bool])->bool:
    if not (env.cassini_ok and env.zeckendorf_ok and env.signature_algorithm=="HMAC-SHA256"): return False
    if not _mode_consistent(env.fold_mode,env.rehydration_count):return False
    expected=hmac.new(signing_key,env.canonical(),hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,env.signature) and verdict_verifier(env.verdict) and witness_verifier(env.witness_receipt_id,env.chain_head) and backend_verifier(env.backend_certificate,env.backend_name)
