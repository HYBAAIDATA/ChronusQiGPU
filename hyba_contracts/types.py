"""Canonical Enterprise schema v2 contracts.

Logical objects are independent from the 64-byte transport ABI. Callable fold
implementations are injected and their stable identifiers are part of the
contract descriptor.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass,field
from enum import Enum
import hashlib,json
from typing import Any,Callable
SCHEMA_VERSION=2
class FoldMode(str,Enum):PRESERVE="PRESERVE";TRANSFORM="TRANSFORM";REHYDRATE="REHYDRATE";REJECT="REJECT"
class BackendClass(str,Enum):CLASSICAL_EXACT="classical_exact";CLASSICAL_APPROX="classical_approx";SIMULATOR="simulator";QUANTUM_HW="quantum_hw"
@dataclass(frozen=True)
class BackendCertificate:
 backend_name:str;backend_class:BackendClass;device_id:str;exactness_modes:tuple[str,...];overflow_behavior:str;supported_operators:tuple[str,...];attestation:str;conformance_hash:str
 def validate(self):
  if self.overflow_behavior!="fail_closed":raise ValueError("backend must fail closed on overflow")
  if not self.attestation or not self.conformance_hash:raise ValueError("backend evidence required")
@dataclass(frozen=True)
class PRIMEObjectV2:
 payload_type:str;lucas_scale:int;pisot_fold:Any;fibonacci_state:tuple[int,int];zeckendorf_code:Any;binet_view:Any;prime_address:int;polyhedral_location:Any;transform_state:Any;cassini_seal:int;lineage_and_time:Any
 object_id:str;tenant:str;instance:str;payload_hash:str;residual_boundary:Any=None;schema_version:int=SCHEMA_VERSION;version:int=1
 def validate(self):
  if self.schema_version!=SCHEMA_VERSION:raise ValueError("unsupported PRIMEObject schema")
  if not all((self.object_id,self.tenant,self.instance,self.payload_hash)):raise ValueError("identity bindings required")
  if self.cassini_seal not in (-1,1):raise ValueError("invalid Cassini seal")
 def canonical(self)->bytes:return json.dumps(asdict(self),sort_keys=True,separators=(",",":"),default=str).encode()
@dataclass(frozen=True)
class FoldContract:
 family:str;domain:str;exactness_mode:str;encode:Callable[[Any],tuple[Any,Any]];decode:Callable[[Any,Any],Any];supported_operators:tuple[str,...];invariant_set:tuple[str,...];residual_bound:str;canonical_hash_rule:str;backend_requirements:tuple[str,...];version:int=1
 def descriptor(self):return {"family":self.family,"domain":self.domain,"exactness_mode":self.exactness_mode,"encode":self.encode.__qualname__,"decode":self.decode.__qualname__,"supported_operators":self.supported_operators,"invariant_set":self.invariant_set,"residual_bound":self.residual_bound,"canonical_hash_rule":self.canonical_hash_rule,"backend_requirements":self.backend_requirements,"version":self.version}
@dataclass(frozen=True)
class OperatorContract:
 operator:str;accepted_fold_families:tuple[str,...];mode:FoldMode;input_invariants:tuple[str,...];output_invariants:tuple[str,...];residual_rule:str;proof_rule:str;deterministic:bool;backend_capabilities:tuple[str,...]
@dataclass(frozen=True)
class ResultReceipt:
 receipt_id:str;operator:str;input_object_id:str;output_object_id:str;mode:FoldMode;rehydration_count:int;residual:Any;invariants_checked:tuple[str,...];proof_id:str;backend_certificate:BackendCertificate;bytes_moved:int;latency_ms:str|None;lineage:tuple[str,...];signature:str
 def validate(self):
  expected=self.mode is FoldMode.REHYDRATE
  if (self.rehydration_count>0)!=expected or self.rehydration_count not in (0,1):raise ValueError("rehydration count/mode mismatch")
  self.backend_certificate.validate()
@dataclass(frozen=True)
class EvidenceObject:
 evidence_id:str;kind:str;subject:str;payload_hash:str;collected_at:int;source:str;signature:str;verify_command:tuple[str,...]
@dataclass(frozen=True)
class EnterprisePolicyContext:
 actor_principal:str;tenant:str;instance:str;purpose:str;residency:str;retention:str;exactness_required:bool;operator_allowed:bool;reconstruction_allowed:bool;training_allowed:bool;export_allowed:bool;degraded_operation_allowed:bool;sovereign_domain:str;classification_level:str
@dataclass(frozen=True)
class HYBAModule:
 module_id:str;version:str;module_type:str;capabilities:tuple[str,...];inputs:tuple[str,...];outputs:tuple[str,...];dependencies:tuple[str,...];incompatible_modules:tuple[str,...];resource_model:dict[str,Any];scale_limits:dict[str,Any];deployment_targets:tuple[str,...];data_classes:tuple[str,...];security_level:str;sovereignty_support:tuple[str,...];compliance_mappings:tuple[str,...];exactness_modes:tuple[str,...];failure_behavior:str;observability_contract:dict[str,Any];evidence_contract:dict[str,Any];upgrade_contract:dict[str,Any];conformance_tests:tuple[str,...]

def canonical_hash(value:Any)->str:
 body=asdict(value) if hasattr(value,"__dataclass_fields__") else value
 return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
