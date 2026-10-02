# Chronus mathematical intrinsics (#106)

## Before → after

Before: Aethel exact arithmetic and the OpenCL punch path were useful but outside typed Chronus IR.

After: `chronus.ir.v0.2` validates eight intrinsic nodes, compiles a canonical lowering plan, executes the authoritative reference path or selects a declared backend, extends the existing #104 corpus formats, and feeds results through #105 cross-verification.

## Classification

| Implementation | Classification |
|---|---|
| `aethel/fibonacci.py::fibonacci/lucas` | AUTHORITATIVE_REFERENCE, EXACT |
| `aethel/fibonacci.py::binet_fibonacci` | AUTHORITATIVE_REFERENCE, EXACT, algorithmically independent of fast doubling |
| `aethel/zeckendorf.py::HardenedZeckendorfCodec` | AUTHORITATIVE_REFERENCE, EXACT |
| dedicated `opencl/chronus_math/*` kernels | PHYSICAL_ACCELERATOR, IMPLEMENTED_UNVERIFIED |
| floating φ/ψ calculations | APPROXIMATE; never `BINET_EXACT` |
| monolithic punch routes | LEGACY physical implementation pending case-level qualification |

## Boundaries

- Fibonacci and exact Binet: `0..93` for `u64`; Lucas: `0..92`.
- Zeckendorf is canonical, non-adjacent, 93-bit, and covers the complete `u64` range.
- Cassini consumes backend-produced witnesses; corrupted witnesses fail.
- Pisot/Lucas proposes candidates, legality filters them, and measurement must select a winner. Conventional candidates remain.
- φ weight is explicit approximate binary32.
- Chronus-1 v1.1 receives no new opcodes. Its wide-integer lowering remains unsupported and fails closed; the compiler never emits machine words.
- `cl_khr_fp64` does not certify Float64. The inherited #104 path remains Float32-only and rejects f64.
- OpenCL capability entries remain `PHYSICAL_EVIDENCE_REQUIRED` until numerical comparison and device/driver evidence are captured.
- Zeckendorf encode/decode is `DEVICE_CODEC`, not `FOLDED_NATIVE`. `FOLDED_NATIVE` remains OPEN until operations stay folded, compare semantically, run physically, and beat an appropriate dense baseline.

## Acceptance

```bash
python scripts/check_chronus106.py
```

The command runs #105 (therefore #104), tests exact and approximate boundaries, extends the same corpus authority, and verifies content addressing. Missing hardware and CI remain explicit.
