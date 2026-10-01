# Tensor Capability Manifest

Machine-readable source: `tensor/capability.py::CAPABILITY_MANIFEST`.

The current consolidation adds three evidence classes: software-complete, hardware-evidence-required, and not implemented. In particular, generic Chronus tensor kernels now exist in software, but hardware correctness/performance remains dependent on a physical OpenCL GPU.

## Implemented and tested

- Tensor contracts, fail-closed routing, timing, provenance, and TFLOPS accounting.
- NumPy reference backend.
- Kellogg exact, quantum, and Tensor ML bridges.
- Exact PULVINI/Geodesic Tensor Engine.
- **True partial unfold**: requested indices are reconstructed recursively without full-tensor materialisation.
- MetricTensor factories/walk, declared-only EnergyModel, virtual PhiGPU and non-simulating HybridGPU compatibility facades.
- Profile-driven hybrid Tensor router.
- Folded linear-inference pilot with bit-exact weight custody and measured end-to-end latency/TFLOPS.
- Mining tensor advice remains permutation-only and non-consensus.

## Hardware evidence required

`chronus/kernels/tensor_ops.cl` and `chronus/tensor_compute.py` implement physical OpenCL GPU float32 `matmul`, `add`, `hadamard`, `scale`, and rank-1/rank-2 `kron`. `tensor/backends/chronus_backend.py` exposes them fail-closed. CI verifies the software contract with a runtime test double; a physical GPU run is still required to certify numerical agreement and performance. No CPU OpenCL device may be reported as `chronus-opencl`, and Chronus performs no internal CPU fallback.

Measured TFLOPS remain derived only from declared operation counts divided by measured Tensor runtime. Hashrate is not a TFLOPS source.

## PULVINI boundary

PULVINI fold depth is an exact reversible representation/custody property. It is not automatically a physical byte-compression ratio, an HBM-elimination ratio, or a model-parameter reduction. The folded-inference pilot therefore reports `physical_compression_ratio=None` until physical measurement supports a different value.

## Still not wired by design

- Turing Grover/Hendrix → Tensor contract: no current production Tensor consumer requires it.
- ASI/TOE VQC manifold bridge → Tensor execution: existing manifold bridges remain advisory surfaces.

Use `tensor.capability.render_markdown()` for the detailed machine-readable row set.
