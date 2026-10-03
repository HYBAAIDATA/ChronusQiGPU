"""Bounded autonomous optimisation with rollback, cooldown and durable learning."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json, os
from pathlib import Path
from typing import Any, Callable

class ActionClass(str, Enum):
    SAFE_AUTOMATIC="safe_automatic"
    BOUNDED_EXPERIMENT="bounded_experiment"
    REQUIRES_APPROVAL="requires_approval"
    FORBIDDEN="forbidden"

@dataclass(frozen=True)
class TrialOutcome:
    candidate_id: str
    accepted: bool
    baseline_metric: float
    candidate_metric: float
    improvement: float
    rollback: bool
    reason: str
    timestamp: str

class ClosedLoopOptimizer:
    def __init__(self, path: str|os.PathLike[str], minimum_samples:int=3, min_improvement:float=.05, cooldown_trials:int=3, attempt_limit:int=3):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.minimum_samples=max(1,int(minimum_samples)); self.min_improvement=float(min_improvement)
        self.cooldown_trials=max(0,int(cooldown_trials)); self.attempt_limit=max(1,int(attempt_limit))
        self.state=self._load()
    def _load(self):
        return json.loads(self.path.read_text()) if self.path.is_file() else {"accepted":{},"failures":{},"cooldowns":{},"history":[]}
    def _save(self):
        tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.state,sort_keys=True,indent=2)); os.replace(tmp,self.path)
    def evaluate(self, *, context:str, candidate_id:str, action_class:ActionClass, baseline_samples:list[float], candidate_samples:list[float], apply:Callable[[],None], rollback:Callable[[],None]) -> TrialOutcome:
        if action_class in {ActionClass.REQUIRES_APPROVAL,ActionClass.FORBIDDEN}: raise PermissionError(f"autonomous action denied: {action_class.value}")
        if len(baseline_samples)<self.minimum_samples or len(candidate_samples)<self.minimum_samples: raise ValueError("minimum observation window not satisfied")
        if self.state["cooldowns"].get(context,0)>0:
            self.state["cooldowns"][context]-=1; self._save(); raise RuntimeError("optimisation cooldown active")
        if self.state["failures"].get(candidate_id,0)>=self.attempt_limit: raise RuntimeError("candidate attempt limit reached")
        baseline=sum(baseline_samples)/len(baseline_samples); candidate=sum(candidate_samples)/len(candidate_samples)
        if baseline<=0 or candidate<0: raise ValueError("metrics must be non-negative and baseline positive")
        improvement=(baseline-candidate)/baseline  # lower-is-better latency/cost
        accepted=improvement>=self.min_improvement
        if accepted:
            apply(); self.state["accepted"][context]=candidate_id; reason="measured improvement"
        else:
            rollback(); self.state["failures"][candidate_id]=self.state["failures"].get(candidate_id,0)+1; self.state["cooldowns"][context]=self.cooldown_trials; reason="regression or insufficient improvement"
        out=TrialOutcome(candidate_id,accepted,baseline,candidate,improvement,not accepted,reason,datetime.now(timezone.utc).isoformat())
        self.state["history"].append({"context":context,**asdict(out)}); self._save(); return out
