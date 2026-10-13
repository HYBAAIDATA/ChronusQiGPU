from dataclasses import dataclass
import math

@dataclass(frozen=True)
class TensorType:
    dtype: str
    shape: tuple[int, ...]

    @property
    def bytes(self) -> int:
        return 4 * math.prod(self.shape)


def signature(ir):
    if ir.op == "vector_add":
        t = TensorType("f32", (ir.shape["n"],))
        return (t, t), (t,)
    if ir.op == "reduce_sum_local":
        return (TensorType("f32", (ir.shape["n"],)),), (TensorType("f32", (1,)),)
    if ir.op == "matmul_tiled":
        a = TensorType("f32", (32, 32))
        return (a, a), (a,)
    raise ValueError(ir.op)
