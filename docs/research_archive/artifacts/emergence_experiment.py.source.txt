"""Controlled emergence experiment protocol.

Complexity is the treatment; held-out behavior is the outcome.  The harness
uses matched budgets, multiple seeds, randomized execution order, explicit
ablations, permutation testing, and falsification criteria.  It does not use
the existing programmed emergence_index as a behavioral outcome.
"""
from __future__ import annotations

import hashlib,json,math,random
from dataclasses import asdict,dataclass
from typing import Callable,Mapping,Sequence

@dataclass(frozen=True)
class ComplexityCondition:
    condition_id:str;memory_depth:int;graph_density:float;constraint_count:int;feedback_depth:int
    def __post_init__(self):
        if not self.condition_id or self.memory_depth<=0 or not 0<=self.graph_density<=1 or self.constraint_count<0 or self.feedback_depth<0:
            raise ValueError("invalid complexity condition")
    @property
    def treatment_vector(self)->tuple[float,float,float,float]:
        return (float(self.memory_depth),float(self.graph_density),float(self.constraint_count),float(self.feedback_depth))

@dataclass(frozen=True)
class BehavioralTrial:
    condition_id:str;blind_id:str;seed:int;ablation:str;budget:int;metrics:dict[str,float];aggregate:float

@dataclass(frozen=True)
class EmergenceExperimentReport:
    schema:str;protocol_hash:str;task_ids:tuple[str,...];budget:int;seeds:tuple[int,...]
    condition_means:dict[str,float];ablation_means:dict[str,float]
    low_high_effect:float;integration_gain:float;permutation_p_value:float
    nonlinear_transition_detected:bool;overload_detected:bool;falsified:bool
    falsification_reasons:tuple[str,...];trials:tuple[BehavioralTrial,...]

BehaviorEvaluator=Callable[[ComplexityCondition,int,int,str,tuple[str,...]],Mapping[str,float]]

class EmergenceExperiment:
    ABLATIONS=("none","shuffled_graph","no_feedback")
    def __init__(self,conditions:Sequence[ComplexityCondition],seeds:Sequence[int],task_ids:Sequence[str],budget:int,
                 *,min_effect:float=.05,min_integration_gain:float=.02,permutations:int=2000,randomization_seed:int=2026):
        self.conditions=tuple(conditions);self.seeds=tuple(int(x) for x in seeds);self.task_ids=tuple(str(x) for x in task_ids)
        self.budget=int(budget);self.min_effect=float(min_effect);self.min_integration_gain=float(min_integration_gain)
        self.permutations=int(permutations);self.randomization_seed=int(randomization_seed)
        if len(self.conditions)<3 or len({c.condition_id for c in self.conditions})!=len(self.conditions):raise ValueError("at least three unique conditions required")
        if len(self.seeds)<3 or not self.task_ids or self.budget<=0 or self.permutations<=0:raise ValueError("multiple seeds, tasks, budget, and permutations required")
        if self.min_effect<0 or self.min_integration_gain<0:raise ValueError("effect thresholds must be nonnegative")
    def run(self,evaluator:BehaviorEvaluator)->EmergenceExperimentReport:
        protocol={"conditions":[asdict(c) for c in self.conditions],"seeds":self.seeds,"tasks":self.task_ids,"budget":self.budget,
                  "ablations":self.ABLATIONS,"min_effect":self.min_effect,"min_integration_gain":self.min_integration_gain}
        protocol_hash="sha256:"+hashlib.sha256(json.dumps(protocol,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        jobs=[(c,s,a) for c in self.conditions for s in self.seeds for a in self.ABLATIONS]
        random.Random(self.randomization_seed).shuffle(jobs);trials=[];metric_schema=None
        blind={c.condition_id:hashlib.sha256(f"{protocol_hash}|{c.condition_id}".encode()).hexdigest()[:12] for c in self.conditions}
        for condition,seed,ablation in jobs:
            raw=dict(evaluator(condition,seed,self.budget,ablation,self.task_ids))
            if not raw:raise ValueError("behavior evaluator must return metrics")
            if metric_schema is None:metric_schema=tuple(sorted(raw))
            if tuple(sorted(raw))!=metric_schema:raise ValueError("all trials must use the same behavioral metric schema")
            metrics={k:float(v) for k,v in raw.items()}
            if any(not math.isfinite(v) or not 0<=v<=1 for v in metrics.values()):raise ValueError("behavioral metrics must be finite and in [0,1]")
            aggregate=sum(metrics.values())/len(metrics);trials.append(BehavioralTrial(condition.condition_id,blind[condition.condition_id],seed,ablation,self.budget,metrics,aggregate))
        means={c.condition_id:self._mean([t.aggregate for t in trials if t.condition_id==c.condition_id and t.ablation=="none"]) for c in self.conditions}
        low,high=self.conditions[0].condition_id,self.conditions[-1].condition_id;effect=means[high]-means[low]
        high_struct=[t.aggregate for t in trials if t.condition_id==high and t.ablation=="none"]
        high_ablated={a:self._mean([t.aggregate for t in trials if t.condition_id==high and t.ablation==a]) for a in self.ABLATIONS if a!="none"}
        integration_gain=self._mean(high_struct)-max(high_ablated.values())
        ablation_means={a:self._mean([t.aggregate for t in trials if t.ablation==a]) for a in self.ABLATIONS}
        sequence=[means[c.condition_id] for c in self.conditions];jumps=[b-a for a,b in zip(sequence,sequence[1:])]
        nonlinear=max(jumps)-min(jumps)>=self.min_effect if len(jumps)>1 else False
        overload=sequence[-1]<max(sequence[:-1])-self.min_effect
        low_values=[t.aggregate for t in trials if t.condition_id==low and t.ablation=="none"]
        p=self._permutation_p(low_values,high_struct)
        reasons=[]
        if effect<self.min_effect:reasons.append("high complexity did not exceed low complexity by the minimum effect")
        if integration_gain<self.min_integration_gain:reasons.append("structured integration did not outperform both ablations")
        if p>=.05:reasons.append("low/high difference was not significant under permutation testing")
        return EmergenceExperimentReport("HYBA_EMERGENCE_EXPERIMENT_V1",protocol_hash,self.task_ids,self.budget,self.seeds,means,ablation_means,
            effect,integration_gain,p,nonlinear,overload,bool(reasons),tuple(reasons),tuple(trials))
    def _permutation_p(self,a:list[float],b:list[float])->float:
        observed=abs(self._mean(b)-self._mean(a));combined=a+b;n=len(a);rng=random.Random(self.randomization_seed+1);extreme=0
        for _ in range(self.permutations):
            values=combined[:];rng.shuffle(values);delta=abs(self._mean(values[:n])-self._mean(values[n:]));extreme+=delta>=observed-1e-15
        return (extreme+1)/(self.permutations+1)
    @staticmethod
    def _mean(values:list[float])->float:return sum(values)/len(values) if values else 0.0

DEFAULT_CONDITIONS=(
 ComplexityCondition("low",1,.10,1,0),ComplexityCondition("medium",4,.35,3,2),
 ComplexityCondition("high",9,.70,6,5),ComplexityCondition("overloaded",16,.95,10,8))

__all__=["ComplexityCondition","BehavioralTrial","EmergenceExperimentReport","EmergenceExperiment","DEFAULT_CONDITIONS"]
