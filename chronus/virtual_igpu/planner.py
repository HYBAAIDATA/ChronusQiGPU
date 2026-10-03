"""Evidence-driven representation, placement and geodesic execution planner."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from heapq import heappop, heappush
import math
from typing import Any, Iterable
from .operators import ExecutionClass


def lucas(n: int) -> int:
    if n < 0: raise ValueError("Lucas order must be non-negative")
    a, b = 2, 1
    for _ in range(n): a, b = b, a + b
    return a


def lucas_order_covering(size: int) -> int:
    if size < 1: return 0
    n = 0
    while lucas(n) < size: n += 1
    return n

@dataclass(frozen=True)
class CostVector:
    move: float = 0.0
    unfold: float = 0.0
    refold: float = 0.0
    compute: float = 0.0
    reuse: float = 0.0
    latency: float = 0.0
    contention: float = 0.0
    energy: float | None = None
    def total(self) -> float:
        return self.move + self.unfold + self.refold + self.compute + self.latency + self.contention - self.reuse + (self.energy or 0.0)

@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    adapter_id: str
    operation: str
    execution_class: ExecutionClass
    local_size: tuple[int, ...]
    batch_size: int
    queue_depth: int
    route: tuple[str, ...]
    lucas_order: int
    lucas_capacity: int
    pisot_residual: float
    estimated_cost: CostVector
    basis: str
    def as_dict(self):
        d=asdict(self); d["execution_class"]=self.execution_class.value; d["estimated_cost"]["total"]=self.estimated_cost.total(); return d

class GeodesicScheduler:
    def __init__(self): self.edges: dict[str, list[tuple[str, float]]] = {}
    def connect(self, a: str, b: str, cost: CostVector, bidirectional: bool=True):
        if cost.total() < 0: raise ValueError("geodesic edge cost cannot be negative")
        self.edges.setdefault(a, []).append((b, cost.total()))
        if bidirectional: self.edges.setdefault(b, []).append((a, cost.total()))
    def shortest_path(self, source: str, target: str) -> tuple[tuple[str,...], float]:
        q=[(0.0, source, ())]; seen=set()
        while q:
            cost,node,path=heappop(q)
            if node in seen: continue
            seen.add(node); path=path+(node,)
            if node == target: return path,cost
            for nxt,w in self.edges.get(node, ()): heappush(q,(cost+w,nxt,path))
        raise ValueError(f"no execution route from {source} to {target}")

class ChronusPlanner:
    def __init__(self, ledger=None, min_improvement: float=0.05):
        self.ledger=ledger; self.min_improvement=float(min_improvement)
    def candidates(self, workload, manifests: Iterable[dict[str,Any]], routes: GeodesicScheduler|None=None) -> list[ExecutionPlan]:
        size=max(1, len(str(workload.input).encode()))
        n=lucas_order_covering(size); phi=(1+math.sqrt(5))/2
        plans=[]
        for manifest in manifests:
            if workload.kind.value not in manifest.get("operations", ()): continue
            limits=manifest.get("limits", {}); adapter=manifest["adapter_id"]
            workgroups=tuple(int(v) for v in limits.get("legal_work_group_sizes", (1,)))
            max_batch=max(1,int(limits.get("max_batch_size", lucas(n))))
            route=("intent",adapter); route_cost=0.0
            if routes:
                try: route,route_cost=routes.shortest_path("intent",adapter)
                except ValueError: continue
            for offset, execution_class in enumerate((ExecutionClass.DENSE_NATIVE, ExecutionClass.PARTIAL_UNFOLD, ExecutionClass.FOLDED_NATIVE)):
                capacity=lucas(max(0,n-offset)); batch=min(capacity,max_batch)
                local=(workgroups[min(offset,len(workgroups)-1)],)
                cost=CostVector(compute=1/max(1,batch), latency=route_cost, unfold=0.2 if execution_class==ExecutionClass.PARTIAL_UNFOLD else 0.0, refold=0.2 if execution_class!=ExecutionClass.DENSE_NATIVE else 0.0)
                plans.append(ExecutionPlan(f"{adapter}:{workload.kind.value}:{n}:{offset}",adapter,workload.kind.value,execution_class,local,batch,max(1,min(lucas(offset+2),int(limits.get("max_queue_depth",8)))),tuple(route),n,capacity,phi**(-n),cost,"lucas-pisot bounded candidate"))
        return sorted(plans,key=lambda p:(p.estimated_cost.total(),p.plan_id))
    def select(self, workload, manifests, routes=None) -> ExecutionPlan:
        plans=self.candidates(workload,manifests,routes)
        if not plans: raise ValueError("no legal execution plan")
        if self.ledger:
            history=self.ledger.query(operation=workload.kind.value, limit=200)
            med={}
            for row in history:
                if row.get("wall_time_ns") is not None: med.setdefault(row["adapter_id"],[]).append(row["wall_time_ns"])
            def score(p):
                samples=med.get(p.adapter_id,[])
                return (sum(samples)/len(samples) if samples else float("inf"), p.estimated_cost.total(),p.plan_id)
            plans.sort(key=score)
        return plans[0]
