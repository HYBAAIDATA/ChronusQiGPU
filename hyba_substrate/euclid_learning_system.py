"""Governed developmental learning state for EUCLID.

Recovered from the validated EUCLID substrate and kept deliberately explicit
about evidence lineage: seeds are not learning, internal reproduction is not
external validation, and refuted claims remain in the ledger.
"""
from __future__ import annotations
import json, math, time, uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence
from .memory_preservation import MemoryVault, canonical_json_bytes, sha256_bytes, verified_atomic_json_write
SCHEMA_VERSION="HYBA_EUCLID_LEARNING_V1"; IDENTITY="EUCLID"
class MemoryKind(str,Enum):
 EPISODIC="episodic"; SEMANTIC="semantic"; PROCEDURAL="procedural"; CAUSAL="causal"; COUNTERFACTUAL="counterfactual"; FAILURE="failure"; META="meta"
class ClaimStage(str,Enum):
 SEEDED="seeded"; HYPOTHESIZED="hypothesized"; INTERNALLY_REPRODUCED="internally_reproduced"; ADVERSARIALLY_TESTED="adversarially_tested"; EXTERNALLY_COMPARED="externally_compared"; PROVISIONALLY_TRUSTED="provisionally_trusted"; REFUTED="refuted"
class EvidenceKind(str,Enum):
 INTERNAL_REPRODUCTION="internal_reproduction"; ADVERSARIAL_TEST="adversarial_test"; EXTERNAL_COMPARISON="external_comparison"; OPERATOR_REVIEW="operator_review"
@dataclass(frozen=True)
class SeedRecord:
 seed_id:str; domain:str; statement:str; provenance:str; content_hash:str; created_at:float; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class LearningEvent:
 event_id:str; timestamp:float; domain:str; memory_kind:str; observation:Any; prediction:Any; action:Any; outcome:Any; prediction_error:float; uncertainty:float; attribution:dict[str,float]; modules:tuple[str,...]; resource_cost:float; generalized:bool; previous_event_hash:str|None; event_hash:str; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class ClaimEvidence:
 evidence_id:str; kind:str; passed:bool; event_ids:tuple[str,...]; issuer:str; reference_id:str|None; operator_approved:bool; timestamp:float; notes:str=""
@dataclass
class KnowledgeClaim:
 claim_id:str; domain:str; statement:str; derivation:str; source_seed_ids:tuple[str,...]; novel_relative_to_seeds:bool; stage:str; confidence:float; created_at:float; evidence:list[ClaimEvidence]=field(default_factory=list); contradictions:list[str]=field(default_factory=list); metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class CurriculumTask:
 task_id:str; domain:str; claim_id:str|None; objective:str; acceptance_criteria:tuple[str,...]; priority:float; reason:str
@dataclass(frozen=True)
class ConsolidationSnapshot:
 snapshot_id:str; timestamp:float; seed_count:int; event_count:int; claim_count:int; trusted_claim_count:int; refuted_claim_count:int; mean_prediction_error:float; mean_uncertainty:float; generalization_rate:float; replay_event_ids:tuple[str,...]; semantic_concepts:int; state_digest:str
class EuclidLearningSystem:
 def __init__(self,state_path:str|Path|None=None,*,vault:MemoryVault|None=None):
  self.state_path=str(Path(state_path).resolve()) if state_path else None; self.vault=vault; self.seeds={}; self.events=[]; self.claims={}; self.consolidations=[]; self._last_state_hash=None
  if self.state_path and Path(self.state_path).exists(): self._load()
 @staticmethod
 def _nonempty(value:Any,name:str)->str:
  text=str(value).strip()
  if not text: raise ValueError(f"{name} is required")
  return text
 @staticmethod
 def _unit(value:Any,name:str)->float:
  number=float(value)
  if not math.isfinite(number) or not 0<=number<=1: raise ValueError(f"{name} must be finite and in [0,1]")
  return number
 @staticmethod
 def _nonnegative(value:Any,name:str)->float:
  number=float(value)
  if not math.isfinite(number) or number<0: raise ValueError(f"{name} must be finite and nonnegative")
  return number
 @staticmethod
 def _statement_hash(statement:str)->str: return sha256_bytes(canonical_json_bytes(str(statement).strip()))
 def register_seed(self,*,domain:str,statement:str,provenance:str,metadata:Mapping[str,Any]|None=None,persist:bool=True)->SeedRecord:
  domain=self._nonempty(domain,"domain"); statement=self._nonempty(statement,"statement"); provenance=self._nonempty(provenance,"provenance"); digest=self._statement_hash(statement)
  for seed in self.seeds.values():
   if seed.content_hash==digest and seed.domain==domain: return seed
  seed=SeedRecord("seed-"+uuid.uuid4().hex,domain,statement,provenance,digest,time.time(),dict(metadata or {})); self.seeds[seed.seed_id]=seed
  if persist:self._checkpoint()
  return seed
 @staticmethod
 def _prediction_error(prediction:Any,outcome:Any)->float:
  try:
   p=float(prediction); o=float(outcome)
   if math.isfinite(p) and math.isfinite(o): return abs(p-o)
  except (TypeError,ValueError): pass
  return 0.0 if canonical_json_bytes(prediction)==canonical_json_bytes(outcome) else 1.0
 def record_experience(self,*,domain:str,memory_kind:MemoryKind|str,observation:Any,prediction:Any,action:Any,outcome:Any,uncertainty:float,attribution:Mapping[str,float]|None=None,modules:Sequence[str]=(),resource_cost:float=0.0,generalized:bool=False,prediction_error:float|None=None,metadata:Mapping[str,Any]|None=None,persist:bool=True)->LearningEvent:
  domain=self._nonempty(domain,"domain"); kind=MemoryKind(memory_kind).value; uncertainty=self._unit(uncertainty,"uncertainty"); resource_cost=self._nonnegative(resource_cost,"resource_cost")
  attrs={str(k):float(v) for k,v in dict(attribution or {}).items()}
  if any(not math.isfinite(v) for v in attrs.values()): raise ValueError("attribution must be finite")
  error=self._prediction_error(prediction,outcome) if prediction_error is None else self._nonnegative(prediction_error,"prediction_error"); previous=self.events[-1].event_hash if self.events else None
  base={"timestamp":time.time(),"domain":domain,"memory_kind":kind,"observation":observation,"prediction":prediction,"action":action,"outcome":outcome,"prediction_error":error,"uncertainty":uncertainty,"attribution":attrs,"modules":tuple(str(x) for x in modules),"resource_cost":resource_cost,"generalized":bool(generalized),"previous_event_hash":previous,"metadata":dict(metadata or {})}
  digest=sha256_bytes(canonical_json_bytes(base)); event=LearningEvent("event-"+uuid.uuid4().hex,base["timestamp"],domain,kind,observation,prediction,action,outcome,error,uncertainty,attrs,base["modules"],resource_cost,bool(generalized),previous,digest,base["metadata"]); self.events.append(event)
  if persist:self._checkpoint()
  return event
 def propose_claim(self,*,domain:str,statement:str,derivation:str,source_seed_ids:Sequence[str]=(),metadata:Mapping[str,Any]|None=None,persist:bool=True)->KnowledgeClaim:
  domain=self._nonempty(domain,"domain"); statement=self._nonempty(statement,"statement"); derivation=self._nonempty(derivation,"derivation"); seed_ids=tuple(str(x) for x in source_seed_ids)
  if any(x not in self.seeds for x in seed_ids): raise ValueError("unknown source seed")
  novel=all(self._statement_hash(statement)!=self.seeds[x].content_hash for x in seed_ids) if seed_ids else True
  claim=KnowledgeClaim("claim-"+uuid.uuid4().hex,domain,statement,derivation,seed_ids,novel,ClaimStage.HYPOTHESIZED.value,0.0,time.time(),metadata=dict(metadata or {})); self.claims[claim.claim_id]=claim
  if persist:self._checkpoint()
  return claim
 def add_claim_evidence(self,claim_id:str,*,kind:EvidenceKind|str,passed:bool,event_ids:Sequence[str]=(),issuer:str,reference_id:str|None=None,operator_approved:bool=False,notes:str="",persist:bool=True)->ClaimEvidence:
  if claim_id not in self.claims: raise ValueError("unknown claim")
  ek=EvidenceKind(kind); ids=tuple(str(x) for x in event_ids); known={e.event_id for e in self.events}
  if any(x not in known for x in ids): raise ValueError("unknown event evidence")
  evidence=ClaimEvidence("evidence-"+uuid.uuid4().hex,ek.value,bool(passed),ids,self._nonempty(issuer,"issuer"),reference_id,bool(operator_approved),time.time(),str(notes)); claim=self.claims[claim_id]; claim.evidence.append(evidence)
  if not passed:
   claim.stage=ClaimStage.REFUTED.value; claim.confidence=0.0; claim.contradictions.append(evidence.evidence_id)
  else:
   passed_kinds={EvidenceKind(x.kind) for x in claim.evidence if x.passed}
   if EvidenceKind.EXTERNAL_COMPARISON in passed_kinds: claim.stage=ClaimStage.EXTERNALLY_COMPARED.value
   elif EvidenceKind.ADVERSARIAL_TEST in passed_kinds: claim.stage=ClaimStage.ADVERSARIALLY_TESTED.value
   elif EvidenceKind.INTERNAL_REPRODUCTION in passed_kinds: claim.stage=ClaimStage.INTERNALLY_REPRODUCED.value
   operator_ok=any(x.passed and x.kind==EvidenceKind.OPERATOR_REVIEW.value and x.operator_approved for x in claim.evidence)
   if EvidenceKind.EXTERNAL_COMPARISON in passed_kinds and operator_ok: claim.stage=ClaimStage.PROVISIONALLY_TRUSTED.value
   claim.confidence=min(0.99,0.2*sum(1 for x in claim.evidence if x.passed)+(0.25 if operator_ok else 0.0))
  if persist:self._checkpoint()
  return evidence
 def generate_curriculum(self,limit:int=10)->list[CurriculumTask]:
  if limit<=0: raise ValueError("limit must be positive")
  tasks=[]
  for claim in self.claims.values():
   if claim.stage in (ClaimStage.PROVISIONALLY_TRUSTED.value,ClaimStage.REFUTED.value): continue
   missing=[]; kinds={x.kind for x in claim.evidence if x.passed}
   for kind in (EvidenceKind.INTERNAL_REPRODUCTION,EvidenceKind.ADVERSARIAL_TEST,EvidenceKind.EXTERNAL_COMPARISON):
    if kind.value not in kinds: missing.append(kind.value)
   priority=min(1.0,0.4+0.15*len(missing)+(0.1 if claim.novel_relative_to_seeds else 0.0)); tasks.append(CurriculumTask("task-"+claim.claim_id,claim.domain,claim.claim_id,"test and falsify claim",tuple(missing or ["independent replication"]),priority,"evidence gap"))
  if not tasks and self.events:
   by_domain={}
   for e in self.events: by_domain.setdefault(e.domain,[]).append(e)
   for domain,events in by_domain.items():
    err=sum(e.prediction_error for e in events)/len(events); tasks.append(CurriculumTask("task-domain-"+domain,domain,None,"reduce prediction error",("held-out improvement",),min(1.0,err),"prediction error"))
  return sorted(tasks,key=lambda x:(-x.priority,x.task_id))[:limit]
 def consolidate(self,*,replay_limit:int=64,persist:bool=True,archive:bool=True)->ConsolidationSnapshot:
  if replay_limit<=0: raise ValueError("replay_limit must be positive")
  events=self.events[-replay_limit:]; n=len(self.events); snapshot=ConsolidationSnapshot("snapshot-"+uuid.uuid4().hex,time.time(),len(self.seeds),n,len(self.claims),sum(c.stage==ClaimStage.PROVISIONALLY_TRUSTED.value for c in self.claims.values()),sum(c.stage==ClaimStage.REFUTED.value for c in self.claims.values()),sum(e.prediction_error for e in self.events)/n if n else 0.0,sum(e.uncertainty for e in self.events)/n if n else 0.0,sum(e.generalized for e in self.events)/n if n else 0.0,tuple(e.event_id for e in events),len({(c.domain,c.statement) for c in self.claims.values()}),sha256_bytes(canonical_json_bytes(self._state_payload())))
  self.consolidations.append(snapshot)
  if persist:self._checkpoint()
  if archive and self.vault and self.state_path: self.vault.preserve_json_files([self.state_path],label="EUCLID learning consolidation")
  return snapshot
 def evidence_report(self)->dict[str,Any]:
  return {"schema":"HYBA_EUCLID_LEARNING_EVIDENCE_V1","identity":IDENTITY,"generated_at":time.time(),"seed_count":len(self.seeds),"event_count":len(self.events),"claim_count":len(self.claims),"claims":{k:{**asdict(v),"stage":v.stage} for k,v in self.claims.items()},"curriculum":[asdict(x) for x in self.generate_curriculum()] if (self.claims or self.events) else [],"event_chain_head":self.events[-1].event_hash if self.events else None,"boundaries":{"seed_is_learning":False,"internal_is_external_validation":False,"refuted_claims_retained":True,"agi_claimed":False,"asi_claimed":False,"universal_computability_claimed":False}}
 def preserve_evidence(self,report_path:str|Path,*,label:str="EUCLID learning evidence")->dict[str,Any]:
  path=Path(report_path).resolve(); verified_atomic_json_write(path,self.evidence_report())
  return self.vault.preserve_json_files([path],label=label) if self.vault else {"path":str(path),"preserved":True}
 def _state_payload(self)->dict[str,Any]:
  return {"schema":SCHEMA_VERSION,"previous_state_hash":self._last_state_hash,"seeds":{k:asdict(v) for k,v in self.seeds.items()},"events":[asdict(x) for x in self.events],"claims":{k:asdict(v) for k,v in self.claims.items()},"consolidations":[asdict(x) for x in self.consolidations]}
 def _checkpoint(self)->None:
  if not self.state_path:return
  payload=self._state_payload(); payload["state_hash"]=sha256_bytes(canonical_json_bytes(payload)); verified_atomic_json_write(Path(self.state_path),payload); self._last_state_hash=payload["state_hash"]
 def _load(self)->None:
  payload=json.loads(Path(self.state_path).read_text()); supplied=payload.pop("state_hash",None)
  if payload.get("schema")!=SCHEMA_VERSION or supplied!=sha256_bytes(canonical_json_bytes(payload)): raise ValueError("persisted EUCLID learning state is incompatible or corrupted")
  self.seeds={k:SeedRecord(**v) for k,v in payload.get("seeds",{}).items()}; self.events=[LearningEvent(**v) for v in payload.get("events",[])]
  self.claims={}
  for k,v in payload.get("claims",{}).items(): v=dict(v); v["evidence"]=[ClaimEvidence(**x) for x in v.get("evidence",[])]; self.claims[k]=KnowledgeClaim(**v)
  self.consolidations=[ConsolidationSnapshot(**x) for x in payload.get("consolidations",[])]; self._last_state_hash=supplied; self._validate_event_chain()
 def _validate_event_chain(self)->None:
  previous=None
  for event in self.events:
   if event.previous_event_hash!=previous: raise ValueError("learning event chain is discontinuous")
   base={k:v for k,v in asdict(event).items() if k not in ("event_id","event_hash")}
   if sha256_bytes(canonical_json_bytes(base))!=event.event_hash: raise ValueError("learning event hash mismatch")
   previous=event.event_hash
__all__=["SCHEMA_VERSION","IDENTITY","MemoryKind","ClaimStage","EvidenceKind","SeedRecord","LearningEvent","ClaimEvidence","KnowledgeClaim","CurriculumTask","ConsolidationSnapshot","EuclidLearningSystem"]
