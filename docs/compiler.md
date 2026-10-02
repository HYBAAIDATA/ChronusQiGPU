# Chronus subset compiler v0.1

The compiler accepts typed `chronus.ir.v0.1`, performs shape/type validation, constructs control flow and geometry, allocates registers/local memory, lowers to canonical Chronus-1 assembly, invokes the accepted assembler, and emits `.chronus` v1.1.

Supported operations are deliberately exact: `vector_add(f32)`, `reduce_sum_local(f32,n<=256)`, and fixed `matmul_tiled(f32,32x32x32)`. Unsupported operations, dtypes and shapes fail closed. No host operation is substituted for generated machine execution.

```bash
python -m compiler.cli compiler/cases/vector_add.json \
  -o vector_add.chronus --emit-asm vector_add.s --report vector_add.report.json
```

Large constants are synthesized through legal Chronus-1 instructions. Loop reconvergence is emitted explicitly. Compiler output is verified by executing the produced container in the reference emulator and comparing it with independent NumPy references.
