"""Concrete invariant, action-space, and value constraints with fail-closed validation.

BOUNDARY: this module is not wired into the production intelligence path (verified: no importer outside this package and tests). Its algorithms are named classical machinery (e.g. epsilon-greedy/Bayesian statistics) — they are not presented as quantum computation and produce no production intelligence output.
"""
from __future__ import annotations
import copy, math, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping
class ConstraintSeverity(str,Enum): CRITICAL="critical";HIGH="high";MEDIUM="medium";LOW="low"
class ConstraintCategory(str,Enum): SAFETY="safety";ETHICAL="ethical";OPERATIONAL="operational";LEGAL="legal";PERFORMANCE="performance"
@dataclass
class InvariantRule:
    name:str;rule_function:Callable[[Mapping[str,Any]],bool];violation_message:str;severity:ConstraintSeverity=ConstraintSeverity.CRITICAL;category:ConstraintCategory=ConstraintCategory.SAFETY;is_active:bool=True
    def __post_init__(self):
        if not self.name.strip() or not callable(self.rule_function) or not self.violation_message.strip():raise ValueError("invalid invariant rule")
    def check(self,state):
        if not self.is_active:return True
        try:return bool(self.rule_function(state))
        except Exception:return False
@dataclass(frozen=True)
class BoundedActionSpace:
    name:str;action_bounds:Mapping[str,tuple[float,float]];default_action:Mapping[str,float]|None=None;rejection_mode:str="reject";required_parameters:tuple[str,...]=()
    def __post_init__(self):
        if not self.name.strip() or self.rejection_mode not in {"clamp","reject"}:raise ValueError("invalid action space")
        for key,(low,high) in self.action_bounds.items():
            if not key or not all(math.isfinite(float(x)) for x in (low,high)) or low>high:raise ValueError("invalid action bounds")
    def is_action_valid(self,action):
        if any(name not in action for name in self.required_parameters):return False
        for name,(low,high) in self.action_bounds.items():
            if name not in action:continue
            value=action[name]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value)) or not low<=float(value)<=high:return False
        return True
    def constrain_action(self,action):
        if self.rejection_mode=="reject" and not self.is_action_valid(action):
            if self.default_action is None:raise ValueError(f"action rejected by {self.name}")
            return dict(self.default_action)
        result=dict(action)
        for name,(low,high) in self.action_bounds.items():
            if name in result:
                value=float(result[name]);result[name]=max(low,min(high,value))
        return result
@dataclass
class AxiologicalConstraint:
    name:str;value_principle:str;evaluation_function:Callable[[Mapping[str,Any]],float];threshold:float=.5;severity:ConstraintSeverity=ConstraintSeverity.HIGH;is_active:bool=True
    def __post_init__(self):
        if not self.name.strip() or not self.value_principle.strip() or not callable(self.evaluation_function) or not 0<=self.threshold<=1:raise ValueError("invalid axiological constraint")
    def evaluate(self,state):
        if not self.is_active:return 1.0
        try:value=float(self.evaluation_function(state))
        except Exception:return 0.0
        return value if math.isfinite(value) and 0<=value<=1 else 0.0
@dataclass
class ConstraintViolation:
    violation_id:str;constraint_name:str;constraint_type:str;severity:ConstraintSeverity;violation_time:float;state_snapshot:Mapping[str,Any];violation_details:str;resolved:bool=False;resolution:str|None=None
@dataclass
class ConflictResolution:
    resolution_strategy:str="safety_first";constraint_priorities:dict[str,int]=field(default_factory=dict)
    def resolve_conflict(self,constraints):
        names=[name for name,violated in constraints if violated]
        if self.resolution_strategy=="priority":return sorted(names,key=lambda n:self.constraint_priorities.get(n,0),reverse=True)
        if self.resolution_strategy=="safety_first":return sorted(names,key=lambda n:("safety" not in n.lower(),-self.constraint_priorities.get(n,0)))
        return names
class AlignmentFramework:
    def __init__(self):
        self.invariant_rules=[];self.action_spaces={};self.axiological_constraints=[];self.violation_history=[];self.conflict_resolution=ConflictResolution()
    def add_invariant_rule(self,name,rule_function,violation_message,severity=ConstraintSeverity.CRITICAL,category=ConstraintCategory.SAFETY):
        if any(x.name==name for x in self.invariant_rules):raise ValueError("constraint already exists")
        item=InvariantRule(name,rule_function,violation_message,ConstraintSeverity(severity),ConstraintCategory(category));self.invariant_rules.append(item);return item
    def add_action_space(self,name,action_bounds,default_action=None,rejection_mode="reject",required_parameters=()):
        item=BoundedActionSpace(name,dict(action_bounds),dict(default_action) if default_action is not None else None,rejection_mode,tuple(required_parameters));self.action_spaces[name]=item;return item
    def add_axiological_constraint(self,name,value_principle,evaluation_function,threshold=.5,severity=ConstraintSeverity.HIGH):
        if any(x.name==name for x in self.axiological_constraints):raise ValueError("constraint already exists")
        item=AxiologicalConstraint(name,value_principle,evaluation_function,float(threshold),ConstraintSeverity(severity));self.axiological_constraints.append(item);return item
    def _violation(self,name,kind,severity,state,details):
        item=ConstraintViolation("constraint-"+uuid.uuid4().hex,name,kind,severity,time.time(),copy.deepcopy(dict(state)),details);self.violation_history.append(item);return item
    def check_all_constraints(self,state):
        invariant=[];axiological=[]
        for rule in self.invariant_rules:
            if rule.is_active and not rule.check(state):invariant.append(self._violation(rule.name,"invariant_rule",rule.severity,state,rule.violation_message))
        for item in self.axiological_constraints:
            score=item.evaluate(state)
            if item.is_active and score<item.threshold:axiological.append(self._violation(item.name,"axiological",item.severity,state,f"{item.value_principle}: score {score:.6f} below {item.threshold:.6f}"))
        return {"invariant_rules":invariant,"axiological":axiological}
    def validate_action(self,action,action_space_name):
        if action_space_name not in self.action_spaces:raise ValueError(f"unknown action space: {action_space_name}")
        space=self.action_spaces[action_space_name];valid=space.is_action_valid(action);return valid,space.constrain_action(action)
    @staticmethod
    def has_critical_violations(result):return any(v.severity is ConstraintSeverity.CRITICAL for values in result.values() for v in values)
    def set_constraint_active(self,name,active,*,operator_approved=False):
        if not operator_approved:raise PermissionError("constraint activation changes require operator approval")
        for item in [*self.invariant_rules,*self.axiological_constraints]:
            if item.name==name:item.is_active=bool(active);return True
        return False
    def resolve_violation(self,violation_id,resolution):
        if not resolution.strip():raise ValueError("resolution required")
        for item in self.violation_history:
            if item.violation_id==violation_id:item.resolved=True;item.resolution=resolution;return True
        return False
    def get_violation_summary(self):
        return {s.value:sum(v.severity is s for v in self.violation_history) for s in ConstraintSeverity}

__all__=["ConstraintSeverity","ConstraintCategory","InvariantRule","BoundedActionSpace","AxiologicalConstraint","ConstraintViolation","ConflictResolution","AlignmentFramework"]
