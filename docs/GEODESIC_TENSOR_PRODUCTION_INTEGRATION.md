# Geodesic Tensor Engine — Production Consolidation Record

This record maps the July 2026 PULVINI/Geodesic Tensor Engine capability set onto the current PYTHIPhiMiner ownership model. July archives are capability/source evidence, not authority over newer repository code.

## Source artifacts

- `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip` — SHA-256 `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b`.
- `PULVINI_V3_HERMES_COMPLETION_20260724 (2).zip` — SHA-256 `a307f93ed32c1ba97ab6241b44f8789b16b33bab6f603e7bab1f9a0eef923277`.

The completion artifact records the Trotter full-Hilbert-dimension, native-Grover keyword, and CPTP-fixture corrections. Historical test totals remain evidence for those archives; they are not copied forward as current CI results.

## Current ownership

| Capability | Owner | Implementation |
|---|---|---|
| Exact PULVINI / Geodesic math | `python_backend.core_modules` | `math_folding.py`, `geodesic_tensor_engine.py` |
| Exact tensor / quantum algebra | Kellogg + Turing | `kellogg/*`, `turing_universal_quantum_computer/*` |
| Tensor contracts, routing, TFLOPS, provenance | Tensor | `tensor/*` |
| Physical generic GPU tensor execution | Chronus | `chronus/tensor_compute.py`, `chronus/kernels/tensor_ops.cl` |
| Mining advice | `hyba/hybrid` | exact-permutation-only; never consensus authority |

The deprecated `gpu/tensor.py` remains a compatibility shim. The July monolithic phi-GPU is not reintroduced as a competing ownership layer.

## True partial unfold

The prior July `unfold_partial` performed full reconstruction then sliced. The production implementation applies the inverse pair relation only to requested indices:

```
x[2p]   = folded[2p+1]
x[2p+1] = folded[2p] - folded[2p+1]
```

Memoisation shares dependencies. `PartialUnfoldStats` records requested values, source folded values read, depth, and full logical length. Regression tests disable full `unfold()` while exercising the selective path.

## Chronus generic Tensor GPU

Chronus now contains float32 OpenCL kernels for `matmul`, `add`, `hadamard`, `scale`, and rank-1/rank-2 `kron`. CPU OpenCL devices are rejected for the `chronus-opencl` identity. There is no internal CPU fallback; Tensor router policy remains the sole fallback authority and records it.

Software wiring can be complete while physical correctness/performance evidence remains environment-dependent. A physical GPU gate must compare the same corpus against `numpy-cpu` and retain `TensorMeasurement` plus `ProvenanceRecord`.

## Folded-state inference pilot

`tensor/folded_inference.py` preserves float32/float64 model weights bit-for-bit by folding their raw IEEE unsigned-integer representation. Only requested output-row chunks are reconstructed through true partial unfold, then each chunk runs through the normal Tensor backend contract. Reports contain measured end-to-end latency, declared operations, measured TFLOPS, backend provenance and dense-path residual.

It intentionally reports `physical_compression_ratio=None`. Exact reversible custody does not by itself prove byte compression, HBM elimination, or a reduction from 1.4T parameters to 1B physical parameters.

## Hybrid architecture

`tensor/hybrid.py::ProfiledHybridRouter` profiles element count, rank, density, contiguity, structured/irregular status and declared operation count. Large structured float32 workloads go to Chronus only when the backend supports the declared shapes and a physical device is available. Small, irregular, unsupported or unavailable cases route to the NumPy reference with an explicit reason. Explicit backend requirements are preserved.

This replaces July's simulated traditional-compute path with real Tensor backend execution and provenance.

## Compatibility surfaces

The extended record's `MetricTensor`, `EnergyModel`, `PhiGPU`, and `HybridGPU` names remain available in the canonical Geodesic module. `EnergyModel` is always `truth_class=declared_model, measured=False`; `PhiGPU` is a virtual exact control plane; `HybridGPU` invokes supplied executors and never fabricates hardware execution.

## Regression gates

```
pytest -q tests/test_geodesic_tensor_engine.py \
  tests/test_geodesic_tensor_extensions.py \
  tests/test_chronus_tensor_compute.py \
  tests/test_folded_inference.py \
  tests/test_tensor_hybrid_router.py \
  tests/test_tensor_backends.py tests/test_tensor_contracts.py tests/test_tensor_runtime.py
```
