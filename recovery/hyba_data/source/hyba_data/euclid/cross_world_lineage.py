"""Cross-World Research Lineage 1: immutable paired laboratory attestation."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Mapping,Any
from .kairos_runtime import _hash
@dataclass(frozen=True)
class WorldAttestation:
 world_id:str;world_hash:str;chronicle_head:str|None;claim:str
@dataclass(frozen=True)
class PairedAttestation:
 lineage_id:str;status:str;envelope_hash:str|None;reasons:tuple[str,...];mining:WorldAttestation|None;millennium:WorldAttestation|None
class CrossWorldLineage:
 def attest(self,lineage_id:str,mining_state:Mapping[str,Any],millennium_state:Mapping[str,Any],relationship:str,*,coherence=True,truth_evidence=True,causal=True,feedback=True)->PairedAttestation:
  if not lineage_id.strip() or not relationship.strip():return PairedAttestation(lineage_id,'VETOED',None,('identity_or_relationship',),None,None)
  def att(s,claim):return WorldAttestation(str(s['world_id']),str(s['world_hash']),s.get('chronicle_head'),claim)
  mining,millennium=att(mining_state,'bounded stability observation'),att(millennium_state,'bounded mathematical invariant experiment')
  gates={'coherence':coherence,'truth_evidence':truth_evidence,'causal_attribution':causal,'feedback_processing':feedback};reasons=tuple(n for n,p in gates.items() if not p)
  if reasons:return PairedAttestation(lineage_id,'VETOED',None,reasons,mining,millennium)
  body={'schema':'EUCLID_CROSS_WORLD_PAIRED_ATTESTATION_V1','lineage_id':lineage_id,'relationship':relationship,'mining':asdict(mining),'millennium':asdict(millennium),'gates':gates,'claim_boundary':'Paired attestations only; no state transfer, cross-world mutation, causal proof, prediction, or control.'}
  return PairedAttestation(lineage_id,'ATTESTED',_hash(body),(),mining,millennium)
