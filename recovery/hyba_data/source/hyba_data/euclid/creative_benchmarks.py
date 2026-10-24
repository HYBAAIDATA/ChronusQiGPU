"""Evidence-bounded creative-intelligence benchmark contracts for EUCLID."""
from __future__ import annotations
import math
from dataclasses import asdict,dataclass,field
from typing import Any,Callable,Mapping,Sequence
import numpy as np
from .creative_substrate import CreatorDirective,EuclidCreativeKernel,MODALITIES,_hash

@dataclass(frozen=True)
class BenchmarkInteraction:
 event_type:str;payload:Mapping[str,Any]
@dataclass(frozen=True)
class CreativeBenchmarkCase:
 case_id:str;directives:tuple[CreatorDirective,...];modalities:tuple[str,...]=MODALITIES;interactions:tuple[BenchmarkInteraction,...]=();expected_themes:tuple[str,...]=();held_out:bool=True
 def __post_init__(self):
  if not self.case_id or not self.directives or not self.modalities:raise ValueError('benchmark case identity, directives and modalities required')
@dataclass(frozen=True)
class ExternalBaseline:
 system_id:str;evaluator_id:str;case_scores:Mapping[str,float];matched_budget:bool;held_out:bool;evidence_hash:str
 def __post_init__(self):
  if not self.system_id or not self.evaluator_id or self.evaluator_id.lower() in {'euclid','hyba','internal'}:raise ValueError('independent evaluator required')
  if not self.matched_budget or not self.held_out:raise ValueError('matched budget and held-out baseline required')
  if not self.evidence_hash.startswith('sha256:') or len(self.evidence_hash)!=71:raise ValueError('external evidence hash required')
  if any(not math.isfinite(float(x)) or not 0<=float(x)<=1 for x in self.case_scores.values()):raise ValueError('baseline scores must be finite in [0,1]')
@dataclass(frozen=True)
class CaseResult:
 case_id:str;intent_fidelity:float;coherence:float;rule_compliance:float;continuity:float;novelty_under_constraints:float;provenance_integrity:float;aggregate:float;world_version:int;world_hash:str
@dataclass(frozen=True)
class BenchmarkReport:
 schema:str;case_results:tuple[CaseResult,...];aggregate:float;external_delta:float|None;claim_lane:str;external_evidence_hash:str|None;limitations:tuple[str,...];report_hash:str

class CreativeBenchmarkSuite:
 """Runs held-out internal probes and accepts only independent matched baselines."""
 def __init__(self,kernel_factory:Callable[[],EuclidCreativeKernel]=EuclidCreativeKernel):self.kernel_factory=kernel_factory
 def run(self,cases:Sequence[CreativeBenchmarkCase],baseline:ExternalBaseline|None=None)->BenchmarkReport:
  items=tuple(cases)
  if not items or len({x.case_id for x in items})!=len(items):raise ValueError('unique benchmark cases required')
  results=[]
  for case in items:
   kernel=self.kernel_factory();cycle=kernel.run(case.directives,modalities=case.modalities)
   initial_states={key:dict(value.state) for key,value in cycle.world.entities.items() if value.kind=='character'}
   for interaction in case.interactions:cycle=kernel.adapt_world(cycle,interaction.event_type,interaction.payload)
   themes=set(cycle.intent.themes);theme_score=len(themes&set(case.expected_themes))/max(1,len(case.expected_themes)) if case.expected_themes else 1.
   continuity=float(np.mean([all(initial_states.get(key,{}).items()<=dict(value.state).items() for key,value in cycle.world.entities.items() if key in initial_states)])) if initial_states else 1.
   allowed=[p.novelty*p.coherence for p in cycle.emergence if p.allowed];novelty=float(np.mean(allowed)) if allowed else 0.
   metrics=(cycle.telemetry.intent_fidelity,cycle.coherence.aggregate,cycle.coherence.world_rule_compliance,continuity,novelty,float(cycle.provenance_verified));aggregate=float(np.mean(metrics)*theme_score)
   results.append(CaseResult(case.case_id,*map(float,metrics),aggregate,cycle.world.version,cycle.world.content_hash))
  overall=float(np.mean([x.aggregate for x in results]));external_delta=None;lane='INTERNAL';evidence=None;limitations=['Internal execution is not independent validation.','Creator satisfaction requires human evaluation and is not inferred.','Rendered-media quality requires deployed providers.']
  if baseline is not None:
   if not all(case.held_out for case in items):raise ValueError('external comparison requires held-out cases')
   missing=set(x.case_id for x in items)-set(baseline.case_scores)
   if missing:raise ValueError(f'baseline missing cases: {sorted(missing)}')
   baseline_mean=float(np.mean([baseline.case_scores[x.case_id] for x in results]));external_delta=overall-baseline_mean;lane='BOUNDED_EXTERNAL_COMPARISON';evidence=baseline.evidence_hash
  payload={'schema':'EUCLID_CREATIVE_BENCHMARK_V1','case_results':[asdict(x) for x in results],'aggregate':overall,'external_delta':external_delta,'claim_lane':lane,'external_evidence_hash':evidence,'limitations':limitations}
  return BenchmarkReport(payload['schema'],tuple(results),overall,external_delta,lane,evidence,tuple(limitations),_hash(payload))

__all__=['BenchmarkInteraction','CreativeBenchmarkCase','ExternalBaseline','CaseResult','BenchmarkReport','CreativeBenchmarkSuite']
