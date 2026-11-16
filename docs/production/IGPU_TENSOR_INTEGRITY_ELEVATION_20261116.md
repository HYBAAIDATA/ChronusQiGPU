# Chronus iGPU/Tensor mathematical and device-integrity elevation

**Scope:** targeted changes to existing OpenCL tensor backend, not a new GPU
engine and not a change to TURING, PYTHIA, OVID, THESEUS, AL HARAS or
the protected PULVINI formal operator.

**Source:** current GitHub `HYBAAIDATA/ChronusQiGPU` `main`, 16 Nov 2026,
cross-checked against the owner's attached iGPU/tensor review and
the corresponding existing implementation.

## Source changes

- The `tensor_matmul` and `tensor_kron2` OpenCL work-item coordinates
  are now `col=get_global_id(0)`, `row=get_global_id(1)`, with matching
  global ND-range shapes. Adjacent x-lanes address contiguous output
  columns for row-major storage; this is an indexing change, not a measured
  throughput improvement.
- OpenCL startup now runs actual physical-device known-answer checks for
  **add, hadamard, scale, non-square matmul, rectangular Kronecker**.
  Small integer-valued float32 fixtures have exact expected outputs.
  One failed operation makes the backend unavailable; no CPU fallback.
- Explicit optional `CHRONUS_OPENCL_DEVICE_MATCH` matches unique device
  identity using name/vendor/driver. No match or ambiguous match fails.
  An OpenCL GPU cannot automatically be labelled an integrated GPU.
- Rejects non-native float32 input, so complex and fp64 inputs cannot be
  silently narrowed to the hardware float32 kernels.
- Bounds matrix and Kronecker outputs to 16,777,216 float32 elements,
  and enforces unsigned 32-bit kernel element-count limits.
- Every produced device result is independently checked against the
  reference operation before return. Matrix multiplication uses a
  componentwise floating-point error bound of the Higham form,
  `gamma_(2k) * (abs(A) @ abs(B))` for conservative coverage of
  non-fused multiply/add, with allowance for the float64
  reference computation and a small absolute float32 subnormal
  rounding allowance; flush-to-zero that exceeds this bound is refused.
  Reference verification is **included in the application latency**
  and cannot be reported as GPU-only speed.

## Important measurement and claim limits

**No actual GPU device, GPU kernel performance, latency reduction, energy
reduction, memory compression, iGPU identity or customer production claim has
been newly measured or qualified by the source-only work.**

The code-level tests exercise the host numerical verifier, dtype refusal,
kernel mapping, and presence of operation checks. A separate optional
hardware-executed test skips only without an OpenCL GPU; a discovered
GPU with a failed kernel build or known-answer qualification fails rather
than skipping. A skip is
**UNAVAILABLE**, not a successful device qualification.

The generic `TopologicalIntegrityGate.verify()` remains a strict
matching-dtype verifier for reference operations. The new explicit
`verify_float32_matmul()` is used only for the GPU matmul's bounded
numerical comparison. No unjustified generic tolerance widening.

## Remaining research and implementation defects not closed by this patch

The supplied review also identified the legacy DMRG solver's hard-coded
two-site state and independently supplied analytic energy, invented planner
FLOPs/memory, no true group-charge decomposition, CUDA's naive kernels,
missing fp64/complex GPU contraction, zero-copy, tiling, and exact
cyclotomic integer GEMM. This OpenCL patch does **not** certify any of
those items. Treat measured hardware speedup, E3 variational DMRG and
full-system production qualification as **UNVERIFIED** until actual
matching implementation, tests and device run evidence exist.

## Reproducibility

Tests: `tests/test_igpu_tensor_integrity_20261116.py`.
Entry source: `src/chronus/tensor/opencl_backend.py`;
physical kernels: `src/chronus/kernels/tensor_ops.cl`;
mathematical verifier: `src/chronus/tensor/geodesic.py`.

References: [Khronos OpenCL ND-range work-item specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html);
[Higham/Pranesh 2019 on low-precision matrix multiplication error bounds](https://epubs.siam.org/doi/pdf/10.1137/19M1251308);
[Manchester numerical analysis note on `gamma_k` and matrix products](https://eprints.maths.manchester.ac.uk/2780/1/paper.pdf).
