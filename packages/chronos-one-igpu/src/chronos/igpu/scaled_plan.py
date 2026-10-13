"""Executable, streaming Lucas scaling for native and host-overlay iGPU paths."""
from dataclasses import dataclass, asdict
from ..lucas_engine import lucas
LADDER = (10,12,15,18,20,31,50,76,110)
@dataclass(frozen=True)
class ScaledPlan:
    base_items: int
    scale_index: int = 15
    start: int = 0
    lanes: int = 32
    address_limit: int = 2**32
    def __post_init__(self):
        if self.scale_index not in LADDER: raise ValueError('undeclared Lucas rung')
        if any(type(x) is not int for x in (self.base_items,self.start,self.lanes,self.address_limit)):
            raise ValueError('integer plan dimensions required')
        if self.base_items < 0 or self.lanes < 1 or not 0 <= self.start <= self.address_limit: raise ValueError('invalid plan')
    @property
    def factor(self): return lucas(self.scale_index)
    @property
    def effective_items(self): return min(self.base_items*self.factor,self.address_limit-self.start)
    @property
    def tile_items(self): return max(1,min(self.effective_items or 1,max(self.lanes,self.factor-self.factor%self.lanes)))
    def chunks(self, max_chunk_items=None):
        width=self.tile_items if max_chunk_items is None else min(self.tile_items,max_chunk_items)
        if type(width) is not int or width < 1: raise ValueError('positive chunk limit required')
        pos=self.start; stop=pos+self.effective_items
        while pos < stop:
            end=min(stop,pos+width); yield (pos,end); pos=end
    def manifest(self):
        return {**asdict(self),'logical_device':'chronos_igpu','lucas_factor':self.factor,
                'effective_items':self.effective_items,'tile_items':self.tile_items,
                'streamed':True,'physical_throughput_multiplier':None}
