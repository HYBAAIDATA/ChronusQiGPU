"""Governed redundancy, graceful degradation, isolation, and verified recovery."""
from __future__ import annotations
import math, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

class FallbackMode(str, Enum): FULL="full"; DEGRADED="degraded"; MINIMAL="minimal"; EMERGENCY="emergency"
class ModuleStatus(str, Enum): OPERATIONAL="operational"; DEGRADED="degraded"; FAILED="failed"; ISOLATED="isolated"

@dataclass(frozen=True)
class ExecutionAttempt:
    attempt_id:str; timestamp:float; path:str; success:bool; elapsed_ms:float; error:str|None

@dataclass
class FallbackHeuristic:
    heuristic_name:str
    primary_function:Callable[[Mapping[str,Any]],Any]
    fallback_function:Callable[[Mapping[str,Any]],Any]
    max_attempts:int=3
    timeout_ms:float=1000.0
    attempts:list[ExecutionAttempt]=field(default_factory=list)
    def __post_init__(self):
        if not self.heuristic_name.strip() or not callable(self.primary_function) or not callable(self.fallback_function): raise ValueError("invalid heuristic")
        if self.max_attempts<=0 or not math.isfinite(self.timeout_ms) or self.timeout_ms<=0: raise ValueError("invalid attempt/timeout limits")
    def _call(self,fn,path,state):
        started=time.perf_counter()
        try:
            result=fn(state); elapsed=(time.perf_counter()-started)*1000
            if elapsed>self.timeout_ms: raise TimeoutError(f"soft timeout exceeded: {elapsed:.3f}ms")
            self.attempts.append(ExecutionAttempt(uuid.uuid4().hex,time.time(),path,True,elapsed,None)); return result
        except Exception as exc:
            elapsed=(time.perf_counter()-started)*1000
            self.attempts.append(ExecutionAttempt(uuid.uuid4().hex,time.time(),path,False,elapsed,f"{type(exc).__name__}: {exc}")); raise
    def execute(self,state:Mapping[str,Any])->tuple[Any,bool]:
        errors=[]
        for _ in range(self.max_attempts):
            try:return self._call(self.primary_function,"primary",state),False
            except Exception as exc:errors.append(str(exc))
        try:return self._call(self.fallback_function,"fallback",state),True
        except Exception as exc:errors.append(str(exc)); raise RuntimeError(f"all paths failed for {self.heuristic_name}: {' | '.join(errors)}") from exc
    def get_failure_rate(self,window_seconds:float=60)->float:
        if window_seconds<=0: raise ValueError("window_seconds must be positive")
        recent=[a for a in self.attempts if time.time()-a.timestamp<=window_seconds]
        return sum(not a.success for a in recent)/len(recent) if recent else 0.0

@dataclass(frozen=True)
class DegradedOperationMode:
    mode_name:str; enabled_modules:tuple[str,...]=(); disabled_modules:tuple[str,...]=()
    reduced_precision_modules:Mapping[str,float]=field(default_factory=dict)
    timeout_multiplier:float=2.0; resource_limit_factor:float=.5
    def __post_init__(self):
        if not self.mode_name.strip() or self.timeout_multiplier<=0 or not 0<self.resource_limit_factor<=1: raise ValueError("invalid degraded mode")
        if set(self.enabled_modules)&set(self.disabled_modules): raise ValueError("module cannot be both enabled and disabled")
        if any(not 0<float(v)<=1 for v in self.reduced_precision_modules.values()): raise ValueError("precision factors must be in (0,1]")
    def is_module_enabled(self,name:str)->bool:
        return name not in self.disabled_modules and (not self.enabled_modules or name in self.enabled_modules)
    def get_precision_factor(self,name:str)->float:return float(self.reduced_precision_modules.get(name,1.0))

@dataclass
class ModuleIsolation:
    module_name:str; isolation_reason:str; isolation_time:float
    status:ModuleStatus=ModuleStatus.ISOLATED; recovery_attempts:int=0; max_recovery_attempts:int=3; recovery_interval_seconds:float=60.0
    def can_attempt_recovery(self,now:float|None=None)->bool:
        return self.recovery_attempts<self.max_recovery_attempts and (now or time.time())-self.isolation_time>=self.recovery_interval_seconds

class RedundancyManager:
    def __init__(self):
        self.current_mode=FallbackMode.FULL; self.fallback_heuristics={}; self.degraded_modes={}; self.isolated_modules={}
        self.health_checks:dict[str,Callable[[],bool]]={}; self.failure_history=[]; self.recovery_history=[]; self.mode_history=[]
    def add_fallback_heuristic(self,name,primary_function,fallback_function,max_attempts=3,timeout_ms=1000)->FallbackHeuristic:
        if name in self.fallback_heuristics: raise ValueError("heuristic already exists")
        item=FallbackHeuristic(name,primary_function,fallback_function,max_attempts,timeout_ms); self.fallback_heuristics[name]=item; return item
    def add_degraded_mode(self,name,enabled_modules=None,disabled_modules=None,reduced_precision_modules=None,timeout_multiplier=2,resource_limit_factor=.5)->DegradedOperationMode:
        item=DegradedOperationMode(name,tuple(enabled_modules or ()),tuple(disabled_modules or ()),dict(reduced_precision_modules or {}),timeout_multiplier,resource_limit_factor)
        self.degraded_modes[name]=item; return item
    def register_health_check(self,module_name:str,health_check:Callable[[],bool])->None:
        if not module_name.strip() or not callable(health_check): raise ValueError("invalid health check")
        self.health_checks[module_name]=health_check
    def isolate_module(self,module_name,reason,max_recovery_attempts=3,recovery_interval_seconds=60)->ModuleIsolation:
        if not str(module_name).strip() or not str(reason).strip() or max_recovery_attempts<=0 or recovery_interval_seconds<0: raise ValueError("invalid isolation")
        item=ModuleIsolation(str(module_name),str(reason),time.time(),max_recovery_attempts=max_recovery_attempts,recovery_interval_seconds=float(recovery_interval_seconds))
        self.isolated_modules[item.module_name]=item; self.failure_history.append((item.module_name,time.time(),item.isolation_reason)); return item
    def execute_with_fallback(self,name,state):
        if name not in self.fallback_heuristics: raise ValueError(f"unknown heuristic: {name}")
        return self.fallback_heuristics[name].execute(state)
    def set_fallback_mode(self,mode:FallbackMode,*,reason:str,operator_approved:bool=False)->None:
        mode=FallbackMode(mode)
        if not reason.strip(): raise ValueError("mode transition reason required")
        if self.current_mode is FallbackMode.EMERGENCY and mode is not FallbackMode.EMERGENCY and not operator_approved: raise PermissionError("leaving emergency mode requires operator approval")
        old=self.current_mode; self.current_mode=mode; self.mode_history.append((time.time(),old.value,mode.value,reason,operator_approved))
        config=self.degraded_modes.get(mode.value)
        if config:
            for name in config.disabled_modules:
                if name not in self.isolated_modules:self.isolate_module(name,f"disabled by mode {mode.value}")
    def check_module_recovery(self,now:float|None=None)->list[str]:
        recovered=[]
        for name,item in list(self.isolated_modules.items()):
            if not item.can_attempt_recovery(now): continue
            item.recovery_attempts+=1; item.isolation_time=now or time.time(); check=self.health_checks.get(name)
            success=False
            try: success=bool(check()) if check else False
            except Exception: success=False
            self.recovery_history.append((name,time.time(),success))
            if success:item.status=ModuleStatus.OPERATIONAL; recovered.append(name); del self.isolated_modules[name]
        return recovered
    def is_module_operational(self,name:str)->bool:
        if name in self.isolated_modules:return False
        config=self.degraded_modes.get(self.current_mode.value); return config.is_module_enabled(name) if config else True
    def get_system_status(self)->dict[str,Any]:
        return {"current_mode":self.current_mode.value,"isolated_modules":sorted(self.isolated_modules),"total_failures":len(self.failure_history),"total_recoveries":sum(x[2] for x in self.recovery_history),"active_heuristics":sorted(self.fallback_heuristics)}

__all__=["FallbackMode","ModuleStatus","ExecutionAttempt","FallbackHeuristic","DegradedOperationMode","ModuleIsolation","RedundancyManager"]
