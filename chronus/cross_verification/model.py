"""Backend-neutral Chronus cross-verification contracts."""
from __future__ import annotations
import hashlib, json, math, struct
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

STATES=frozenset({'VERIFIED','IMPLEMENTED_UNVERIFIED','SOFTWARE_VERIFIED','PHYSICAL_EVIDENCE_REQUIRED','NOT_APPLICABLE','UNSUPPORTED','FAILED'})
RESULTS=frozenset({'PASS','FAIL','NOT_APPLICABLE_TO_TRANSLATED_BACKEND','PHYSICAL_EVIDENCE_REQUIRED','UNSUPPORTED','HARNESS_ERROR'})
def canonical(value:Any)->bytes:return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256(data:bytes)->str:return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class Float32Policy:
 atol:float=1e-5;rtol:float=1e-5;max_ulp:int=8
 nan_rule:str='both-nan';infinity_rule:str='same-sign';signed_zero_rule:str='equal'
 fused_fma_ops:frozenset[str]=frozenset({'vector_add','reduce_sum_local'})
 def compare(self,operation:str,expected:bytes,actual:bytes)->tuple[bool,Mapping[str,Any]]:
  if len(expected)!=len(actual) or len(expected)%4:return False,{'reason':'byte-length'}
  e=struct.unpack(f'<{len(expected)//4}f',expected);a=struct.unpack(f'<{len(actual)//4}f',actual)
  strict=operation in self.fused_fma_ops;worst=0.0
  for index,(x,y) in enumerate(zip(e,a)):
   if math.isnan(x) or math.isnan(y):
    if not(math.isnan(x) and math.isnan(y)):return False,{'reason':'nan','index':index}
    continue
   if math.isinf(x) or math.isinf(y):
    if x!=y:return False,{'reason':'infinity','index':index}
    continue
   if strict:
    if struct.pack('<f',x)!=struct.pack('<f',y) and not(x==0.0 and y==0.0):return False,{'reason':'fused-bit-pattern','index':index}
   else:
    err=abs(x-y);worst=max(worst,err)
    if err>self.atol+self.rtol*abs(x):return False,{'reason':'tolerance','index':index,'abs_error':err}
  return True,{'strict_fma':strict,'max_abs_error':worst,'signed_zero':self.signed_zero_rule}

@dataclass(frozen=True)
class CapabilityManifest:
 adapter_id:str;backend:str;device:str;hardware_executed:bool
 supported_semantics:Sequence[str];supported_ops:Sequence[str];supported_dtypes:Sequence[str]
 execution_classes:Sequence[str];trap_fidelity:str;profiling:Mapping[str,Any]
 verification_state:Mapping[str,str];driver:str='';runtime:str='';compiler:str='';physical_evidence_digest:str|None=None
 def validate(self)->None:
  if not self.adapter_id or not self.backend or not self.device:raise ValueError('backend identity is required')
  if any(v not in STATES for v in self.verification_state.values()):raise ValueError('unknown verification state')
  if set(self.verification_state)-set(self.supported_ops):raise ValueError('verification state for undeclared operation')
  if self.hardware_executed and (not self.driver or not self.runtime or not self.physical_evidence_digest):raise ValueError('hardware execution requires driver, runtime and physical evidence')
  if self.hardware_executed and any(v in {'IMPLEMENTED_UNVERIFIED','SOFTWARE_VERIFIED','PHYSICAL_EVIDENCE_REQUIRED'} for v in self.verification_state.values()):raise ValueError('hardware claim contradicts verification state')
 def as_dict(self)->Mapping[str,Any]:
  self.validate();return {'schema':'chronus.backend-capability.v1','adapter_id':self.adapter_id,'backend':self.backend,'device':self.device,'hardware_executed':self.hardware_executed,'supported_semantics':list(self.supported_semantics),'supported_ops':list(self.supported_ops),'supported_dtypes':list(self.supported_dtypes),'execution_classes':list(self.execution_classes),'trap_fidelity':self.trap_fidelity,'profiling':dict(self.profiling),'verification_state':dict(self.verification_state),'driver':self.driver,'runtime':self.runtime,'compiler':self.compiler,'physical_evidence_digest':self.physical_evidence_digest}
 @property
 def digest(self)->str:return sha256(canonical(self.as_dict()))

@dataclass(frozen=True)
class Execution:
 status:str;output:bytes|None=None;trap:str|None=None;trace:bytes|None=None
 translated_artifact:bytes|None=None;physical_evidence:Mapping[str,Any]|None=None;metadata:Mapping[str,Any]=field(default_factory=dict)
