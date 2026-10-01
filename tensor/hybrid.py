"""Profile-driven hybrid routing between reference and Chronus tensor compute."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .backends import BackendRegistry
from .contracts import Precision, TensorOperationSpec, TensorRequest
from .engine import execute as execute_tensor
from .router import default_registry


@dataclass(frozen=True)
class WorkloadProfile:
    operation:str; total_input_elements:int; max_rank:int; density:float
    all_contiguous:bool; structured:bool; declared_operations:int


@dataclass(frozen=True)
class HybridRouteDecision:
    backend:str; reason:str; profile:WorkloadProfile; hardware_available:bool


@dataclass(frozen=True)
class HybridExecution:
    decision:HybridRouteDecision; result:Any


class ProfiledHybridRouter:
    def __init__(self,*,min_elements_for_hardware:int=4096,min_operations_for_hardware:int=100_000,
                 min_density:float=0.25):
        if min_elements_for_hardware<1 or min_operations_for_hardware<0: raise ValueError("hybrid routing thresholds are invalid")
        if not 0.0<=min_density<=1.0: raise ValueError("min_density must be in [0, 1]")
        self.min_elements=int(min_elements_for_hardware); self.min_operations=int(min_operations_for_hardware)
        self.min_density=float(min_density)

    def profile(self,operation:TensorOperationSpec,inputs:Sequence[Any],*,structured_hint:bool|None=None):
        arrays=[np.asarray(v) for v in inputs]; total=sum(int(a.size) for a in arrays)
        rank=max((a.ndim for a in arrays),default=0); nonzero=sum(int(np.count_nonzero(a)) for a in arrays)
        density=nonzero/max(total,1); contiguous=all(bool(a.flags.c_contiguous) for a in arrays)
        inferred=(operation.name in {"matmul","add","scale","hadamard","kron"}
                  and density>=self.min_density and rank<=2)
        structured=inferred if structured_hint is None else bool(structured_hint)
        return WorkloadProfile(operation.name,total,rank,density,contiguous,structured,operation.op_count)

    def choose(self,operation,inputs,*,registry:BackendRegistry|None=None,structured_hint=None):
        registry=registry if registry is not None else default_registry(); profile=self.profile(operation,inputs,structured_hint=structured_hint)
        if operation.dtype is not Precision.FLOAT32:
            return HybridRouteDecision("numpy-cpu","Chronus generic kernels currently certify float32 only",profile,False)
        if not profile.structured: return HybridRouteDecision("numpy-cpu","workload classified irregular",profile,False)
        if profile.total_input_elements<self.min_elements:
            return HybridRouteDecision("numpy-cpu","workload below hardware element threshold",profile,False)
        if profile.declared_operations<self.min_operations:
            return HybridRouteDecision("numpy-cpu","workload below hardware operation threshold",profile,False)
        chronus=registry.get("chronus-opencl")
        if not chronus.supports(operation):
            return HybridRouteDecision("numpy-cpu","Chronus does not support declared operation/shape",profile,False)
        available=bool(chronus.is_available())
        if not available: return HybridRouteDecision("numpy-cpu","physical Chronus tensor device unavailable",profile,False)
        return HybridRouteDecision("chronus-opencl","structured workload exceeds thresholds and hardware is available",profile,True)

    def execute(self,request:TensorRequest,inputs:Sequence[Any],*,registry:BackendRegistry|None=None,
                structured_hint=None,model=None):
        registry=registry if registry is not None else default_registry()
        if request.backend_required is not None:
            profile=self.profile(request.operation,inputs,structured_hint=structured_hint); backend=registry.get(request.backend_required)
            decision=HybridRouteDecision(request.backend_required,"explicit backend requirement preserved",profile,bool(backend.is_available()))
            return HybridExecution(decision,execute_tensor(request,inputs,registry=registry,model=model))
        decision=self.choose(request.operation,inputs,registry=registry,structured_hint=structured_hint)
        routed=replace(request,backend_required=decision.backend,allow_fallback=False)
        return HybridExecution(decision,execute_tensor(routed,inputs,registry=registry,model=model))


__all__=["HybridExecution","HybridRouteDecision","ProfiledHybridRouter","WorkloadProfile"]
