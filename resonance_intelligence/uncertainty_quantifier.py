"""Validated Bayesian uncertainty estimation without self-certifying claims.

BOUNDARY: this module is not wired into the production intelligence path (verified: no importer outside this package and tests). Its algorithms are named classical machinery (e.g. epsilon-greedy/Bayesian statistics) — they are not presented as quantum computation and produce no production intelligence output.
"""
from __future__ import annotations
import math
from dataclasses import dataclass,field
from typing import Any,Mapping
import numpy as np
@dataclass(frozen=True)
class UncertaintyEstimate:
 epistemic:float;aleatoric:float;total:float;confidence:float;prediction:Any=None;metadata:dict[str,Any]=field(default_factory=dict)
@dataclass
class BayesianNode:
 name:str;prior_mean:float=0.;prior_variance:float=1.;observation_variance:float=1.;posterior_mean:float=0.;posterior_variance:float=1.;count:int=0
 def __post_init__(self):
  if self.prior_variance<=0 or self.observation_variance<=0:raise ValueError("variances must be positive")
  self.posterior_mean=self.prior_mean;self.posterior_variance=self.prior_variance
 def observe(self,value:float):
  value=float(value)
  if not math.isfinite(value):raise ValueError("observation must be finite")
  prior_precision=1/self.posterior_variance;data_precision=1/self.observation_variance
  self.posterior_variance=1/(prior_precision+data_precision);self.posterior_mean=self.posterior_variance*(prior_precision*self.posterior_mean+data_precision*value);self.count+=1
class BayesianNetwork:
 def __init__(self):self.nodes={}
 def add_node(self,name,prior_mean=0.,prior_variance=1.,observation_variance=1.):
  if not name or name in self.nodes:raise ValueError("unique node name required")
  self.nodes[name]=BayesianNode(name,prior_mean,prior_variance,observation_variance);return self.nodes[name]
 def observe(self,name,value):
  if name not in self.nodes:raise KeyError(name)
  self.nodes[name].observe(value)
class UncertaintyQuantifier:
 def __init__(self,uncertainty_threshold=.3,max_history=1000,seed=0):
  if not 0<=uncertainty_threshold<=1 or max_history<=0:raise ValueError("invalid uncertainty controls")
  self.uncertainty_threshold=uncertainty_threshold;self.max_history=max_history;self.network=BayesianNetwork();self.history=[];self.rng=np.random.default_rng(seed)
 def add_variable(self,*args,**kwargs):return self.network.add_node(*args,**kwargs)
 def record_observation(self,name,value):self.network.observe(name,value)
 @staticmethod
 def _unit(value,label):
  value=float(value)
  if not math.isfinite(value) or not 0<=value<=1:raise ValueError(f"{label} must be finite in [0,1]")
  return value
 def estimate_uncertainty(self,prediction,context:Mapping[str,Any]|None=None,prediction_variance:float|None=None):
  context=dict(context or {});used=[]
  for name,value in context.items():
   if name in self.network.nodes:self.network.observe(name,value);used.append(self.network.nodes[name].posterior_variance)
  epistemic=self._unit(float(np.mean(used)) if used else float(context.get("epistemic",.5)),"epistemic")
  aleatoric=self._unit(prediction_variance if prediction_variance is not None else context.get("noise_level",.2),"aleatoric")
  total=min(1.,epistemic+aleatoric);estimate=UncertaintyEstimate(epistemic,aleatoric,total,1-total,prediction,{"observed_nodes":len(used)})
  self.history.append(estimate);self.history=self.history[-self.max_history:];return estimate
 def get_exploration_probability(self,state):return self.estimate_uncertainty(state.get("prediction"),state).epistemic
 def should_explore(self,state):return bool(self.rng.random()<self.get_exploration_probability(state))
 def calibrate_uncertainty_threshold(self,target_exploration_rate,operator_approved=False):
  if not operator_approved:raise PermissionError("operator approval required")
  target=self._unit(target_exploration_rate,"target rate")
  if not self.history:return self.uncertainty_threshold
  self.uncertainty_threshold=float(np.quantile([x.epistemic for x in self.history],1-target));return self.uncertainty_threshold
 def get_uncertainty_summary(self):
  if not self.history:return {"total_estimates":0}
  return {"total_estimates":len(self.history),"avg_epistemic":float(np.mean([x.epistemic for x in self.history])),"avg_aleatoric":float(np.mean([x.aleatoric for x in self.history])),"avg_total":float(np.mean([x.total for x in self.history]))}
