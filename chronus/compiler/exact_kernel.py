"""Integer Chronus IR: fused recurrences and portable, overflow-defined lowering.

Each iteration reads indices[i] and writes a disjoint output row. This affine
access contract proves fusion/interchange of the independent outer iterations.
All arithmetic results are residues modulo 2**32 on every emitted target.
"""

from dataclasses import dataclass
from typing import Mapping
from chronus.lucas_engine import fibonacci_pair, lucas
from chronus.mla1517.scaling import padovan

MASK = (1 << 32) - 1
OUTPUTS = ("fibonacci", "lucas", "padovan", "golden_stride", "cassini")


@dataclass(frozen=True)
class ExactKernelIR:
    outputs: tuple[str, ...] = OUTPUTS
    tile_items: int = 128

    def __post_init__(self):
        if (
            not self.outputs
            or any(v not in OUTPUTS for v in self.outputs)
            or len(set(self.outputs)) != len(self.outputs)
        ):
            raise ValueError("outputs must be distinct declared recurrence results")
        if type(self.tile_items) is not int or not 1 <= self.tile_items <= 256:
            raise ValueError("tile_items must be in 1..256")

    @classmethod
    def from_dict(cls, value: Mapping):
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "outputs", "tile_items"}
            or value["schema"] != "chronus.exact_ir/v1"
        ):
            raise ValueError("invalid exact IR schema")
        if not isinstance(value["outputs"], list):
            raise ValueError("IR outputs must be a list")
        return cls(tuple(value["outputs"]), value["tile_items"])

    def to_dict(self):
        return {
            "schema": "chronus.exact_ir/v1",
            "outputs": list(self.outputs),
            "tile_items": self.tile_items,
        }

    def legality(self):
        return {
            "iteration_domain": "0<=i<n",
            "read": "indices[i]",
            "write": f"output[{len(self.outputs)}*i+j],0<=j<{len(self.outputs)}",
            "cross_iteration_dependencies": [],
            "fusion_legal": True,
            "overflow": "modulo_2^32",
            "tile_working_bytes": self.tile_items * (1 + len(self.outputs)) * 4,
        }

    def admit(self, indices, seed):
        if not isinstance(indices, list) or not 1 <= len(indices) <= 65536:
            raise ValueError("indices must contain 1..65536 items")
        if any(type(n) is not int or not 0 <= n <= 1024 for n in indices):
            raise ValueError("recurrence indices must be in 0..1024")
        if type(seed) is not int or not 0 <= seed <= MASK:
            raise ValueError("seed must be uint32")

    def reference(self, indices, seed=0):
        self.admit(indices, seed)
        rows = []
        for i, n in enumerate(indices):
            f, _ = fibonacci_pair(n)
            values = {
                "fibonacci": f,
                "lucas": lucas(n),
                "padovan": padovan(n),
                "golden_stride": seed + i * 0x9E3779B9,
                "cassini": 4 * (-1 if n % 2 else 1),
            }
            rows.append([values[name] & MASK for name in self.outputs])
        return rows

    def execute(self, indices, seed=0):
        self.admit(indices, seed)
        rows = []
        for start in range(0, len(indices), self.tile_items):
            for i in range(start, min(start + self.tile_items, len(indices))):
                n = indices[i]
                a, b, p, q, r = 0, 1, 1, 1, 1
                for k in range(n):
                    a, b = b, (a + b) & MASK
                    if k >= 2:
                        p, q, r = q, r, (p + q) & MASK
                ell = (2 * b - a) & MASK
                values = {
                    "fibonacci": a,
                    "lucas": ell,
                    "padovan": r,
                    "golden_stride": (seed + i * 0x9E3779B9) & MASK,
                    "cassini": (ell * ell - 5 * a * a) & MASK,
                }
                rows.append([values[name] for name in self.outputs])
        return rows

    def lower(self, target):
        expressions = {
            "fibonacci": "a",
            "lucas": "ell",
            "padovan": "r",
            "golden_stride": "seed+i*0x9E3779B9u",
            "cassini": "ell*ell-5u*a*a",
        }
        writes = "\n".join(
            f"output[{len(self.outputs)}u*i+{j}u]={expressions[name]};"
            for j, name in enumerate(self.outputs)
        )
        body = """uint count=indices[i];
uint a=0u,b=1u,p=1u,q=1u,r=1u;
for(uint k=0u;k<count;++k){uint next=a+b;a=b;b=next;
if(k>=2u){uint nextp=p+q;p=q;q=r;r=nextp;}}
uint ell=2u*b-a;
""" + writes
        if target == "c":
            return (
                """#include <stdint.h>
typedef uint32_t uint;
void chronus_kernel(const uint *restrict indices,uint n,uint seed,uint *restrict output){
"""
                + f"for(uint tile=0;tile<n;tile+={self.tile_items}u){{\n"
                + f"uint stop=tile+{self.tile_items}u;if(stop>n)stop=n;\n"
                + "#pragma omp simd\nfor(uint i=tile;i<stop;++i){\n"
                + body
                + "\n}}}\n"
            )
        if target == "opencl":
            return (
                "__kernel void chronus_kernel(__global const uint *indices,uint n,uint seed,__global uint *output){uint i=get_global_id(0);if(i>=n)return;\n"
                + body
                + "\n}\n"
            )
        if target == "metal":
            return (
                "#include <metal_stdlib>\nusing namespace metal;\nkernel void chronus_kernel(device const uint *indices [[buffer(0)]],constant uint &n [[buffer(1)]],constant uint &seed [[buffer(2)]],device uint *output [[buffer(3)]],uint i [[thread_position_in_grid]]){if(i>=n)return;\n"
                + body
                + "\n}\n"
            )
        if target == "glsl":
            return (
                "#version 450\n"
                + f"layout(local_size_x={self.tile_items}) in;\n"
                + """layout(set=0,binding=0,std430) readonly buffer Input {uint indices[];};
layout(set=0,binding=1,std430) writeonly buffer Output {uint results[];};
layout(push_constant) uniform Parameters {uint n;uint seed;};
void main(){uint i=gl_GlobalInvocationID.x;if(i>=n)return;
"""
                + body.replace("output[", "results[")
                + "\n}\n"
            )
        raise ValueError("unknown lowering target")
