from dataclasses import dataclass
@dataclass(frozen=True)
class Block:name:str;successors:tuple[str,...]
def construct(ir):
 if ir.op=='vector_add':return (Block('entry',()),)
 if ir.op=='reduce_sum_local':return (Block('entry',('reduce_loop',)),Block('reduce_loop',('reduce_loop','reduce_done')),Block('reduce_done',()))
 if ir.op=='matmul_tiled':return (Block('entry',('tile_loop',)),Block('tile_loop',('k_loop',)),Block('k_loop',('k_loop','k_done')),Block('k_done',('tile_loop','tile_done')),Block('tile_done',()))
 raise ValueError(ir.op)
def validate_reconvergence(ir,asm):
 conditional=sum(1 for line in asm.splitlines() if line.strip().startswith(('BRAZ ','BRANZ ')))
 records=sum(1 for line in asm.splitlines() if line.strip().startswith('.reconv '))
 if conditional!=records:raise ValueError('lowering emitted incomplete reconvergence metadata')
