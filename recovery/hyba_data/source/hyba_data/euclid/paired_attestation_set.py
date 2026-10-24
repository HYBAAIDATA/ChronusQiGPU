"""Cross-World Lineage 1B evidence-set manifest; aggregation only."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Mapping
from .cross_world_lineage import PairedAttestation
from .kairos_runtime import _hash
@dataclass(frozen=True)
class PairedAttestationSet:
 set_id:str;declared_positive:int;declared_negative:int;artifacts:tuple[PairedAttestation,...]
 def manifest(self)->Mapping[str,object]:
  if not self.set_id.strip():raise ValueError('set identity required')
  p=[a for a in self.artifacts if a.status=='ATTESTED'];n=[a for a in self.artifacts if a.status=='VETOED'];f={}
  for a in n:
   for r in a.reasons:f[r]=f.get(r,0)+1
  body={'schema':'EUCLID_PAIRED_ATTESTATION_SET_V1','set_id':self.set_id,'declared':{'positive':self.declared_positive,'negative':self.declared_negative},'actual':{'positive':len(p),'negative':len(n)},'failure_distribution':f,'artifact_hashes':[a.envelope_hash for a in self.artifacts],'complete':len(p)==self.declared_positive and len(n)==self.declared_negative,'claim_boundary':'Evidence aggregation only; no compatibility mapping, causal conclusion, prediction, cross-world mutation, transfer, or federation.'}
  return {**body,'manifest_hash':_hash(body)}
