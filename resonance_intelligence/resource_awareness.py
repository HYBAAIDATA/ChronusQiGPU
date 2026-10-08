"""Resource-bounded allocation and strategy selection.

BOUNDARY: this module is not wired into the production intelligence path (verified: no importer outside this package and tests). Its algorithms are named classical machinery (e.g. epsilon-greedy/Bayesian statistics) — they are not presented as quantum computation and produce no production intelligence output.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum
class QualityMode(str,Enum):MAXIMUM="maximum";BALANCED="balanced";FAST="fast";MINIMAL="minimal"
@dataclass
class ResourceBudget:
 max_time_ms:float;max_compute_units:float;max_memory_mb:float;current_time_ms:float=0.;current_compute_units:float=0.;current_memory_mb:float=0.
 def __post_init__(self):
  if any(not math.isfinite(x) or x<=0 for x in (self.max_time_ms,self.max_compute_units,self.max_memory_mb)):raise ValueError("positive finite budgets required")
 def consume(self,time_ms=0.,compute_units=0.,memory_mb=0.):
  values=(time_ms,compute_units,memory_mb)
  if any(not math.isfinite(x) or x<0 for x in values):raise ValueError("consumption must be finite and nonnegative")
  self.current_time_ms+=time_ms;self.current_compute_units+=compute_units;self.current_memory_mb=max(self.current_memory_mb,memory_mb)
 def is_exhausted(self):return self.current_time_ms>=self.max_time_ms or self.current_compute_units>=self.max_compute_units or self.current_memory_mb>=self.max_memory_mb
class ResourceAwareIntelligence:
 def __init__(self):self.quality_mode=QualityMode.BALANCED;self.current_budget=None;self.modules={};self.strategies={}
 def set_resource_budget(self,max_time_ms,max_compute_units,max_memory_mb):self.current_budget=ResourceBudget(max_time_ms,max_compute_units,max_memory_mb);return self.current_budget
 def register_module(self,name,priority,base_compute=0.):
  if not name or not math.isfinite(priority) or priority<0 or base_compute<0:raise ValueError("invalid module allocation")
  self.modules[name]=(priority,base_compute)
 def allocate_compute(self,available_compute):
  if not math.isfinite(available_compute) or available_compute<0:raise ValueError("invalid compute")
  total=sum(p for p,_ in self.modules.values())
  if total<=0:return {n:0. for n in self.modules}
  return {n:available_compute*p/total for n,(p,_) in self.modules.items()}
 def register_strategy(self,name,cost_function,benefit_function):self.strategies[name]=(cost_function,benefit_function)
 def select_strategy(self,names,state):
  if not names:raise ValueError("strategy list required")
  remaining=self.current_budget.max_compute_units-self.current_budget.current_compute_units if self.current_budget else math.inf;candidates=[]
  for name in names:
   if name not in self.strategies:continue
   cost=float(self.strategies[name][0](state));benefit=float(self.strategies[name][1](state))
   if all(math.isfinite(x) for x in (cost,benefit)) and 0<=cost<=remaining:candidates.append((benefit-cost,name))
  if not candidates:raise RuntimeError("no feasible strategy")
  return max(candidates)[1]
 def is_budget_exhausted(self):return bool(self.current_budget and self.current_budget.is_exhausted())
