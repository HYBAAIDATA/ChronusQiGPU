from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Callable, Iterable, TypeVar
T=TypeVar('T')
@dataclass(frozen=True)
class Tile:
    tile_id:int; start:int; end:int
@dataclass(frozen=True)
class HostGPUPlan:
    total_items:int; lanes:int; mode:str='host_gpu_overlay'; backend:str='cpu_reference'; device_count:int=1
    def __post_init__(self):
        if self.total_items<0 or self.lanes<1: raise ValueError('invalid plan')
        if self.mode not in {'standalone','integrated_iGPU','host_gpu_overlay','cpu_reference'}: raise ValueError('unsupported mode')
        if self.device_count != 1: raise ValueError('Chronus is ONE iGPU; device_count must be 1')
    def tiles(self):
        if self.total_items==0:return ()
        count=min(self.lanes,self.total_items); base,extra=divmod(self.total_items,count); out=[]; start=0
        for tile_id in range(count):
            width=base+(1 if tile_id<extra else 0); out.append(Tile(tile_id,start,start+width)); start+=width
        return tuple(out)
    def validate(self):
        ts=self.tiles()
        if self.total_items==0:return
        if not ts or ts[0].start!=0 or ts[-1].end!=self.total_items: raise ValueError('coverage failure')
        if any(a.end!=b.start for a,b in zip(ts,ts[1:])): raise ValueError('gap/overlap')
        if self.device_count != 1: raise ValueError('Chronus is ONE iGPU; device_count must be 1')
    def manifest(self):
        self.validate()
        return {**asdict(self),'tiles':[asdict(t) for t in self.tiles()],'coverage':self.total_items,'one_igpu':True,'logical_device':'chronos_igpu'}
def execute_reference(values:Iterable[T], plan:HostGPUPlan, kernel:Callable[[T],T]):
    items=list(values)
    if len(items)!=plan.total_items: raise ValueError('value count mismatch')
    plan.validate(); out=[None]*len(items)
    for tile in plan.tiles():
        for i in range(tile.start,tile.end): out[i]=kernel(items[i])
    return out
