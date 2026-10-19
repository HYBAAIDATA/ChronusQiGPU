# Chronus subset compiler v0.1

The compiler accepts typed `chronus.ir.v0.1`, validates shape/type, lowers to canonical Chronus-1 assembly, invokes the accepted assembler, and emits `.chronus` v1.1.

The exact supported surface is `vector_add(f32, 1<=n<=4080)`, `reduce_sum_local(f32, 1<=n<=256)`, and `matmul_tiled(f32,32x32x32)`. `vector_add(n=4081)` is rejected during IR validation because its current `B=align64(4n)`, `ONE=align64(B+4n)`, `C=align64(ONE+4)` lowering exceeds the signed immediate path. Float64/f64 and all unsupported schemas, operations, dimensions and dtypes fail closed. No host operation is substituted.

```bash
python scripts/check_chronus103.py
python scripts/check_chronus104.py
```

NumPy is used only by conformance as an independent float32 oracle, never as execution.
