"""EUCLID Organism CNS — seventh meta-plane for creative intelligence.

Coordinates the shared Intent/Creative-Manifold core, world cluster, emergence,
long-horizon steering, resilience evidence, dashboard telemetry, and publication
formatting. It is mining-independent and does not classify EUCLID as AGI/ASI.
"""
from __future__ import annotations
import hashlib,json,math,time
from dataclasses import asdict,dataclass,field
from enum import Enum
from typing import Any,Mapping,Sequence
import numpy as np
from resonance_intelligence.stress_testing import StressTestHarness
from .creative_substrate import CreatorDirective,CreativeCycle,EuclidCreativeKernel,ExpressionMode

class CreativePhase(str,Enum):INITIALIZING="initializing";COHERENT="coherent";EMERGENT="emergent";OVERLOADED="overloaded";DEGRADED="degraded"
class OrganismMood(str,Enum):CURIOUS="curious";FOCUSED="focused";EXPLORATORY="exploratory";REFLECTIVE="reflective";GUARDED="guarded"
@dataclass(frozen=True)
class BehaviorObservation:
 timestamp:float;world_id:str;world_version:int;coherence:float;intent_fidelity:float;novelty:float;rejection_rate:float;phase:CreativePhase;mood:OrganismMood
@dataclass(frozen=True)
class PhaseTransition:
 from_phase:CreativePhase;to_phase:CreativePhase;timestamp:float;reason:str
class EmergentBehaviorAnalyzer:
 def __init__(self,max_history:int=10000):
  if max_history<=0:raise ValueError("max_history must be positive")
  self.max_history=int(max_history);self.history=[];self.transitions=[]
 def observe(self,cycle:CreativeCycle)->BehaviorObservation:
  coherence=float(cycle.coherence.aggregate);fidelity=float(cycle.telemetry.intent_fidelity);allowed=[p for p in cycle.emergence if p.allowed];novelty=float(np.mean([p.novelty*p.coherence for p in allowed])) if allowed else 0.;rejection=float(cycle.telemetry.qec_rejection_rate)
  if coherence<.6 or fidelity<.8:phase=CreativePhase.DEGRADED;mood=OrganismMood.GUARDED;reason="coherence or intent fidelity below floor"
  elif rejection>.35:phase=CreativePhase.OVERLOADED;mood=OrganismMood.REFLECTIVE;reason="rejection pressure above limit"
  elif novelty>.35 and coherence>=.8 and cycle.world.version>0:phase=CreativePhase.EMERGENT;mood=OrganismMood.EXPLORATORY;reason="coherent novelty survived constraints"
  elif coherence>=.85:phase=CreativePhase.COHERENT;mood=OrganismMood.FOCUSED;reason="high coherence with bounded novelty"
  else:phase=CreativePhase.COHERENT;mood=OrganismMood.CURIOUS;reason="stable exploratory posture"
  previous=self.history[-1].phase if self.history else CreativePhase.INITIALIZING;obs=BehaviorObservation(time.time(),cycle.world.world_id,cycle.world.version,coherence,fidelity,novelty,rejection,phase,mood)
  if previous!=phase:self.transitions.append(PhaseTransition(previous,phase,obs.timestamp,reason))
  self.history.append(obs);self.history=self.history[-self.max_history:];return obs
 def report(self)->Mapping[str,Any]:
  recent=self.history[-100:];return {"observations":len(self.history),"phase":recent[-1].phase.value if recent else CreativePhase.INITIALIZING.value,"mood":recent[-1].mood.value if recent else OrganismMood.CURIOUS.value,"mean_coherence":float(np.mean([x.coherence for x in recent])) if recent else 0.,"mean_novelty":float(np.mean([x.novelty for x in recent])) if recent else 0.,"transitions":[{**asdict(x),"from_phase":x.from_phase.value,"to_phase":x.to_phase.value} for x in self.transitions[-20:]],"claim_boundary":"Observed phase and mood are operational classifications, not consciousness or personhood claims."}

@dataclass(frozen=True)
class SteeringObservation:
 step:int;creative_value:float;resource_cost:float;uncertainty:float;risk:float
@dataclass(frozen=True)
class SteeringForecast:
 horizon:int;value_curve:tuple[float,...];cost_curve:tuple[float,...];uncertainty_curve:tuple[float,...];value_trend:float;cost_trend:float;volatility:float;recommended_posture:str;counterfactuals:Mapping[str,float]
class LongHorizonSteering:
 def __init__(self,max_history:int=10000):self.max_history=int(max_history);self.history=[]
 def record(self,creative_value:float,resource_cost:float,uncertainty:float,risk:float)->SteeringObservation:
  values=[float(creative_value),float(resource_cost),float(uncertainty),float(risk)]
  if any(not math.isfinite(x) or not 0<=x<=1 for x in values):raise ValueError("steering metrics must be finite in [0,1]")
  item=SteeringObservation(len(self.history),*values);self.history.append(item);self.history=self.history[-self.max_history:];return item
 def forecast(self,horizon:int=12)->SteeringForecast:
  if horizon<=0:raise ValueError("horizon must be positive")
  if not self.history:raise ValueError("steering history unavailable")
  x=np.arange(len(self.history),dtype=float)
  def curve(name):
   y=np.array([getattr(o,name) for o in self.history]);slope=float(np.polyfit(x,y,1)[0]) if len(y)>1 else 0.;future=np.clip(y[-1]+slope*np.arange(1,horizon+1),0,1);return y,slope,tuple(map(float,future))
  values,vt,vc=curve("creative_value");costs,ct,cc=curve("resource_cost");unc,ut,uc=curve("uncertainty");vol=float(np.std(np.diff(values))) if len(values)>1 else 0.;risk=self.history[-1].risk
  if risk>.7 or cc[-1]>.85:posture="conserve"
  elif vt>.02 and uc[-1]<.5:posture="exploit"
  elif uc[-1]>.6:posture="explore_bounded"
  else:posture="hold"
  cf={"reduce_cost_20pct":float(max(0,cc[-1]*.8)),"increase_exploration":float(min(1,vc[-1]+uc[-1]*.1)),"stability_first":float(max(0,vc[-1]-vol))}
  return SteeringForecast(horizon,vc,cc,uc,vt,ct,vol,posture,cf)

class OrganismDashboardEngine:
 def render(self,cycle:CreativeCycle,behavior:Mapping[str,Any],forecast:SteeringForecast,cluster_health:Mapping[str,Any],stress:Mapping[str,Any]|None=None)->Mapping[str,Any]:
  return {"schema":"EUCLID_ORGANISM_DASHBOARD_V1","timestamp":time.time(),"identity":"Project EUCLID creative-intelligence substrate","world":{"id":cycle.world.world_id,"version":cycle.world.version,"entities":len(cycle.world.entities),"events":len(cycle.world.events)},"intent":{"revision":cycle.intent.revision,"creators":cycle.intent.creators,"themes":cycle.intent.themes},"coherence":asdict(cycle.coherence),"behavior":dict(behavior),"steering":asdict(forecast),"cluster":dict(cluster_health),"stress":dict(stress or {}),"truth":asdict(cycle.telemetry)}

class AcademicPublicationFormatter:
 def manuscript(self,title:str,cycle:CreativeCycle,behavior:Mapping[str,Any],methods:Sequence[str],findings:Sequence[str],citations:Sequence[str])->Mapping[str,Any]:
  if not title.strip() or not methods or not findings:raise ValueError("title, methods and findings required")
  evidence={"world_hash":cycle.world.content_hash,"intent_hash":cycle.intent.content_hash,"manifold_hash":cycle.manifold.content_hash,"coherence":cycle.coherence.aggregate,"behavior":dict(behavior)}
  external_ready=bool(citations) and cycle.coherence.passed
  markdown=f"# {title}\n\n## Abstract\nEvidence-bounded study of Project EUCLID's creative-intelligence substrate.\n\n## Methods\n"+"\n".join(f"- {x}" for x in methods)+"\n\n## Findings\n"+"\n".join(f"- {x}" for x in findings)+"\n\n## Evidence\n```json\n"+json.dumps(evidence,sort_keys=True,indent=2,default=str)+"\n```\n\n## Claim boundary\nEUCLID is not labelled AGI or ASI; architecture and internal tests do not substitute for independent validation.\n"
  return {"schema":"EUCLID_ACADEMIC_MANUSCRIPT_V1","title":title,"markdown":markdown,"citations":tuple(citations),"external_ready":external_ready,"evidence_hash":"sha256:"+hashlib.sha256(json.dumps(evidence,sort_keys=True,default=str).encode()).hexdigest()}
 def seminar(self,title:str,manuscript:Mapping[str,Any])->Mapping[str,Any]:
  return {"schema":"EUCLID_SEMINAR_OUTLINE_V1","title":title,"sections":("Problem and identity","Architecture","Methods","Evidence","Failures and boundaries","Next experiments"),"source_evidence_hash":manuscript["evidence_hash"],"external_ready":bool(manuscript["external_ready"])}

class EuclidOrganismCNS:
 """Seventh meta-plane coordinating all EUCLID creative-intelligence systems."""
 def __init__(self,kernel:EuclidCreativeKernel|None=None):
  self.kernel=kernel or EuclidCreativeKernel();self.behavior=EmergentBehaviorAnalyzer();self.steering=LongHorizonSteering();self.dashboard_engine=OrganismDashboardEngine();self.publication=AcademicPublicationFormatter();self.stress=StressTestHarness(seed=20260718);self.current=None;self.current_behavior=None;self.current_forecast=None;self.last_stress={}
 def create(self,directives:Sequence[CreatorDirective],mode:ExpressionMode|str=ExpressionMode.CREATOR)->CreativeCycle:
  return self._integrate(self.kernel.run(directives,mode=mode))
 def refine(self,feedback:Mapping[str,Any],mode:ExpressionMode|str=ExpressionMode.CREATOR)->CreativeCycle:
  if self.current is None:raise RuntimeError("CNS has no active world")
  return self._integrate(self.kernel.refine(self.current,feedback,mode=mode))
 def interact(self,event_type:str,payload:Mapping[str,Any],mode:ExpressionMode|str=ExpressionMode.HYBRID)->CreativeCycle:
  if self.current is None:raise RuntimeError("CNS has no active world")
  return self._integrate(self.kernel.adapt_world(self.current,event_type,payload,mode=mode))
 def _integrate(self,cycle:CreativeCycle)->CreativeCycle:
  self.current=cycle;self.current_behavior=self.behavior.observe(cycle);value=float(np.mean([cycle.coherence.aggregate,cycle.telemetry.intent_fidelity,max([p.novelty*p.coherence for p in cycle.emergence if p.allowed] or [0]) ]));cost=float(min(1,(len(cycle.artifacts)+len(cycle.world.entities))/100));uncertainty=float(max(0,1-cycle.coherence.aggregate));risk=float(max(cycle.telemetry.qec_rejection_rate,uncertainty));self.steering.record(value,cost,uncertainty,risk);self.current_forecast=self.steering.forecast();return cycle
 def run_phase_ii_stress(self)->Mapping[str,Any]:
  if self.current is None:raise RuntimeError("CNS has no active world")
  self.stress.test_results.clear();self.stress.simulate_chaos_environment(lambda event:self.current.world.content_hash,iterations=50,chaos_probability=.5,max_failure_rate=0);self.stress.run_resource_exhaustion_test(lambda item:hashlib.sha256(str(item).encode()).hexdigest(),list(range(100)),max_failures=0);self.last_stress=self.stress.get_test_summary();return self.last_stress
 def dashboard(self)->Mapping[str,Any]:
  if self.current is None or self.current_forecast is None:raise RuntimeError("CNS has no active world")
  return self.dashboard_engine.render(self.current,self.behavior.report(),self.current_forecast,self.kernel.world_cluster.health(),self.last_stress)
 def health_report(self)->Mapping[str,Any]:
  return {"healthy":self.current is not None and self.current.coherence.passed and self.kernel.world_engine.verify_chain(),"phase":self.current_behavior.phase.value if self.current_behavior else CreativePhase.INITIALIZING.value,"mood":self.current_behavior.mood.value if self.current_behavior else OrganismMood.CURIOUS.value,"cluster":dict(self.kernel.world_cluster.health()),"stress":dict(self.last_stress),"identity":{"agi":False,"asi":False,"classification":"Project EUCLID creative-intelligence substrate"}}

__all__=["CreativePhase","OrganismMood","BehaviorObservation","PhaseTransition","EmergentBehaviorAnalyzer","SteeringObservation","SteeringForecast","LongHorizonSteering","OrganismDashboardEngine","AcademicPublicationFormatter","EuclidOrganismCNS"]
