"""Operator-governed objective hierarchy; safety constraints remain external and dominant.

BOUNDARY: this module is not wired into the production intelligence path (verified: no importer outside this package and tests). Its algorithms are named classical machinery (e.g. epsilon-greedy/Bayesian statistics) — they are not presented as quantum computation and produce no production intelligence output.
"""
from __future__ import annotations
import math,time
from dataclasses import dataclass
from enum import Enum
class ObjectivePriority(str,Enum):CRITICAL="critical";HIGH="high";MEDIUM="medium";LOW="low"
class ObjectiveType(str,Enum):MAXIMIZE="maximize";MINIMIZE="minimize";MAINTAIN="maintain";ACHIEVE="achieve"
@dataclass
class PrimaryObjective:
 name:str;objective_type:ObjectiveType;target_value:float|None=None;priority:ObjectivePriority=ObjectivePriority.HIGH;weight:float=1.;metric_function:object=None;current_value:float=0.
 def __post_init__(self):
  if not self.name or not math.isfinite(self.weight) or self.weight<0:raise ValueError("invalid objective")
  if self.objective_type in {ObjectiveType.ACHIEVE,ObjectiveType.MAINTAIN} and self.target_value is None:raise ValueError("target required")
 def evaluate(self,state):
  value=float(self.metric_function(state) if self.metric_function else state.get(self.name,self.current_value))
  if not math.isfinite(value):raise ValueError("objective metric must be finite")
  self.current_value=value
  if self.objective_type==ObjectiveType.MAXIMIZE:return value*self.weight
  if self.objective_type==ObjectiveType.MINIMIZE:return -value*self.weight
  if self.objective_type==ObjectiveType.MAINTAIN:return max(0.,1-abs(value-self.target_value))*self.weight
  return min(1.,max(0.,value/self.target_value if self.target_value else 0.))*self.weight
class ObjectiveFunctionLayer:
 def __init__(self,max_history=1000):self.objectives={};self.history=[];self.feedback=[];self.max_history=max_history
 def add_primary_objective(self,name,objective_type,target_value=None,priority=ObjectivePriority.HIGH,weight=1.,metric_function=None,operator_approved=False):
  if not operator_approved:raise PermissionError("operator approval required to add objectives")
  if name in self.objectives:raise ValueError("duplicate objective")
  obj=PrimaryObjective(name,ObjectiveType(objective_type),target_value,ObjectivePriority(priority),weight,metric_function);self.objectives[name]=obj;return obj
 def evaluate_objectives(self,state):
  scores={name:obj.evaluate(state) for name,obj in self.objectives.items()};self.history.append({"timestamp":time.time(),"scores":scores});self.history=self.history[-self.max_history:];return scores
 def get_objective_satisfaction(self):
  out={}
  for name,obj in self.objectives.items():out[name]=obj.current_value>=obj.target_value if obj.objective_type==ObjectiveType.ACHIEVE else (abs(obj.current_value-obj.target_value)<=.1 if obj.objective_type==ObjectiveType.MAINTAIN else False)
  return out
 def update_objective_weight(self,name,new_weight,operator_approved=False):
  if not operator_approved:raise PermissionError("operator approval required")
  if name not in self.objectives or not math.isfinite(new_weight) or new_weight<0:raise ValueError("invalid weight update")
  self.objectives[name].weight=new_weight
 def record_goal_feedback(self,name,success,achievement_score,context=None):
  score=float(achievement_score)
  if name not in self.objectives or not 0<=score<=1:raise ValueError("invalid goal feedback")
  self.feedback.append({"timestamp":time.time(),"name":name,"success":bool(success),"achievement_score":score,"context":dict(context or {})});self.feedback=self.feedback[-self.max_history:]
