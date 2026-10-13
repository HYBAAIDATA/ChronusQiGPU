from dataclasses import dataclass
@dataclass(frozen=True)
class Geometry: global_size:tuple[int,int,int];local_size:tuple[int,int,int]
def choose_geometry(ir):
 if ir.op=='vector_add':
  n=ir.shape['n'];local=min(256,n);return Geometry((n,1,1),(local,1,1))
 if ir.op=='reduce_sum_local':
  n=ir.shape['n'];return Geometry((n,1,1),(n,1,1))
 if ir.op=='matmul_tiled':return Geometry((32,32,1),(16,16,1))
 raise ValueError(ir.op)
