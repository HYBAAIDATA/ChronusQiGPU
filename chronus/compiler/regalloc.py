"""Deterministic allocation contracts for the v0.1 lowering templates."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Allocation: registers:tuple[int,...];local_bytes:int;strategy:str='static-linear-v0.1'
def allocate(ir):
 if ir.op=='vector_add':return Allocation(tuple(range(1,11)),0)
 if ir.op=='reduce_sum_local':return Allocation(tuple(range(1,12)),ir.shape['n']*4)
 if ir.op=='matmul_tiled':return Allocation(tuple(range(1,32)),2048)
 raise ValueError(ir.op)
