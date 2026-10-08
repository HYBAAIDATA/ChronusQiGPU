"""Governed exploration/exploitation decisions with deterministic strategies.

BOUNDARY: this module is not wired into the production intelligence path (verified: no importer outside this package and tests). Its algorithms are named classical machinery (e.g. epsilon-greedy/Bayesian statistics) — they are not presented as quantum computation and produce no production intelligence output.
"""
from __future__ import annotations
import math, random, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

class ExplorationMode(str,Enum): EXPLORE="explore"; EXPLOIT="exploit"; BALANCED="balanced"; CONSERVATIVE="conservative"; AGGRESSIVE="aggressive"
class ExplorationStrategy(str,Enum): UNCERTAINTY_THRESHOLD="uncertainty_threshold"; EPSILON_GREEDY="epsilon_greedy"; UPPER_CONFIDENCE_BOUND="upper_confidence_bound"; THOMPSON_SAMPLING="thompson_sampling"; INFORMATION_GAIN="information_gain"
@dataclass(frozen=True)
class ExplorationDecision:
    decision_id:str; mode:ExplorationMode; strategy:ExplorationStrategy; uncertainty:float; reward_trend:float; confidence:float; timestamp:float; rationale:str; metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass
class ExplorationMetrics:
    total_decisions:int=0; explore_count:int=0; exploit_count:int=0; reward_history:list[float]=field(default_factory=list); uncertainty_history:list[float]=field(default_factory=list)

class ExplorationController:
    def __init__(self,default_strategy=ExplorationStrategy.UNCERTAINTY_THRESHOLD,uncertainty_threshold=.7,epsilon=.1,ucb_c=2.0,seed=0,max_history=10000):
        if not 0<=uncertainty_threshold<=1 or not 0<=epsilon<=1 or ucb_c<0 or max_history<=0: raise ValueError("invalid exploration parameters")
        self.default_strategy=ExplorationStrategy(default_strategy);self.uncertainty_threshold=float(uncertainty_threshold);self.epsilon=float(epsilon);self.ucb_c=float(ucb_c)
        self.current_epsilon=float(epsilon);self.decay_rate=.995;self.min_epsilon=.01;self.max_history=int(max_history);self.rng=random.Random(seed);self.metrics=ExplorationMetrics();self.decision_history=[];self.forced_mode:ExplorationMode|None=None
    @staticmethod
    def _finite(value,name):
        value=float(value)
        if not math.isfinite(value):raise ValueError(f"{name} must be finite")
        return value
    def decide(self,uncertainty,reward_trend,strategy=None,context:Mapping[str,Any]|None=None)->ExplorationDecision:
        u=self._finite(uncertainty,"uncertainty");trend=self._finite(reward_trend,"reward_trend")
        if not 0<=u<=1:raise ValueError("uncertainty must be in [0,1]")
        strategy=ExplorationStrategy(strategy or self.default_strategy);ctx=dict(context or {})
        if self.forced_mode:mode=self.forced_mode;rationale="operator-forced mode"
        elif strategy is ExplorationStrategy.UNCERTAINTY_THRESHOLD:
            mode=ExplorationMode.EXPLORE if u>self.uncertainty_threshold or trend<0 else ExplorationMode.EXPLOIT;rationale="uncertainty/reward threshold"
        elif strategy is ExplorationStrategy.EPSILON_GREEDY:
            mode=ExplorationMode.EXPLORE if self.rng.random()<self.current_epsilon else ExplorationMode.EXPLOIT;rationale=f"epsilon={self.current_epsilon:.6f}"
        elif strategy is ExplorationStrategy.UPPER_CONFIDENCE_BOUND:
            count=int(ctx.get("action_count",0));total=int(ctx.get("total_count",0))
            if count<0 or total<0:raise ValueError("counts must be nonnegative")
            bonus=math.inf if count==0 else self.ucb_c*math.sqrt(math.log(max(total,1)+1)/count)
            mode=ExplorationMode.EXPLORE if bonus>float(ctx.get("exploration_gate",.5)) else ExplorationMode.EXPLOIT;rationale=f"ucb_bonus={bonus}"
        elif strategy is ExplorationStrategy.THOMPSON_SAMPLING:
            successes=float(ctx.get("successes",1));failures=float(ctx.get("failures",1))
            if successes<=0 or failures<=0:raise ValueError("beta parameters must be positive")
            sample=self.rng.betavariate(successes,failures);mode=ExplorationMode.EXPLORE if sample<float(ctx.get("exploit_gate",.5)) else ExplorationMode.EXPLOIT;rationale=f"beta_sample={sample:.6f}"
        else:
            gain=float(ctx.get("expected_information_gain",0));
            if not math.isfinite(gain):raise ValueError("information gain must be finite")
            mode=ExplorationMode.EXPLORE if gain>.3 or u>.6 else ExplorationMode.EXPLOIT;rationale=f"information_gain={gain:.6f}"
        item=ExplorationDecision("explore-"+uuid.uuid4().hex,mode,strategy,u,trend,1-u,time.time(),rationale,ctx);self.decision_history.append(item);self.decision_history=self.decision_history[-self.max_history:]
        self.metrics.total_decisions+=1;self.metrics.explore_count+=mode is ExplorationMode.EXPLORE;self.metrics.exploit_count+=mode is ExplorationMode.EXPLOIT;self.metrics.uncertainty_history.append(u);self.metrics.uncertainty_history=self.metrics.uncertainty_history[-self.max_history:]
        self.current_epsilon=max(self.min_epsilon,self.current_epsilon*self.decay_rate);return item
    def record_reward(self,reward):
        value=self._finite(reward,"reward");self.metrics.reward_history.append(value);self.metrics.reward_history=self.metrics.reward_history[-self.max_history:]
    def get_reward_trend(self,window=10):
        if window<=0:raise ValueError("window must be positive")
        values=self.metrics.reward_history
        if len(values)<2*window:return 0.0
        return sum(values[-window:])/window-sum(values[-2*window:-window])/window
    def set_forced_mode(self,mode:ExplorationMode|None,*,operator_approved=False):
        if not operator_approved:raise PermissionError("forcing exploration mode requires operator approval")
        self.forced_mode=None if mode is None else ExplorationMode(mode)
    def set_uncertainty_threshold(self,threshold,*,operator_approved=False):
        if not operator_approved:raise PermissionError("threshold changes require operator approval")
        value=float(threshold)
        if not 0<=value<=1:raise ValueError("threshold must be in [0,1]")
        self.uncertainty_threshold=value
    def get_exploration_statistics(self):
        n=self.metrics.total_decisions
        return {"total_decisions":n,"explore_count":self.metrics.explore_count,"exploit_count":self.metrics.exploit_count,"exploration_rate":self.metrics.explore_count/n if n else 0.0,"current_epsilon":self.current_epsilon,"average_reward":sum(self.metrics.reward_history)/len(self.metrics.reward_history) if self.metrics.reward_history else 0.0,"reward_trend":self.get_reward_trend(),"forced_mode":self.forced_mode.value if self.forced_mode else None}

__all__=["ExplorationMode","ExplorationStrategy","ExplorationDecision","ExplorationMetrics","ExplorationController"]
