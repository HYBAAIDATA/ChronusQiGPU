# Tensor Capability Manifest

Machine-readable source: `tensor/capability.py::CAPABILITY_MANIFEST`.
Regenerate this table with `python3 -c "from tensor.capability import
render_markdown; print(render_markdown())"`.

Statuses are honest, not aspirational:

- **implemented_tested** — code exists and has passing unit tests in this
  repository checkout.
- **hardware_evidence_required** — the interface exists and fails closed,
  but a real pass requires hardware this sandbox cannot certify. No
  performance or correctness claim is made without that evidence.
- **not_implemented** — intentionally out of scope for this change.

| Feature | Status | Implementation | Tests/Evidence |
|---|---|---|---|
| `contracts.validation` | implemented_tested | `tensor/contracts.py` | tests/test_tensor_contracts.py |
| `backend.numpy_reference` | implemented_tested | `tensor/backends/numpy_backend.py` | tests/test_tensor_backends.py |
| `backend.chronus_adapter` | hardware_evidence_required | `tensor/backends/chronus_backend.py` | tests/test_tensor_backends.py (availability honesty only) |
| `router.explicit_backend_fail_closed` | implemented_tested | `tensor/router.py` | tests/test_tensor_backends.py |
| `router.policy_gated_fallback` | implemented_tested | `tensor/router.py` | tests/test_tensor_backends.py |
| `runtime.timing_cancellation_memory` | implemented_tested | `tensor/runtime.py` | tests/test_tensor_runtime.py |
| `tflops.declared_op_count_only` | implemented_tested | `tensor/contracts.py:TensorMeasurement` | tests/test_tensor_contracts.py |
| `exact.kellogg_exact_tensor` | implemented_tested | `kellogg/exact_tensor.py (bridged via tensor/kellogg_bridge.py)` | tests/test_kellogg_tensor.py |
| `exact.kellogg_quantum_tensor` | implemented_tested | `kellogg/quantum_tensor.py (bridged via tensor/kellogg_bridge.py)` | tests/test_kellogg_tensor.py |
| `exact.kellogg_tensor_ml` | implemented_tested | `kellogg/tensor_ml.py (bridged via tensor/kellogg_bridge.py)` | tests/test_toe_tensor_ml.py |
| `vqc.exact_and_quantum_tensor_loaders` | implemented_tested | `tensor/kellogg_bridge.py:load_exact_tensor_module/load_quantum_tensor_module` | tests/test_tensor_package.py |
| `mining.advisor_boundary` | implemented_tested | `hyba/hybrid/tensor_advisor.py (re-exported by tensor/advisor.py)` | tests/test_three_layer_runtime.py, tests/test_tensor_advisor_safety.py |
| `compat.gpu_tensor_shim` | implemented_tested | `gpu/tensor.py` | tests/test_tensor_gpu_compat.py |
| `packaging.tensor_distribution` | implemented_tested | `pyproject.toml ([tool.setuptools] packages, package-data)` | tests/test_package_layout.py |
| `grover.hendrix_entry_points` | not_implemented | — | No currently-supported Grover/Hendrix tensor entry point was found wired to production code in this audit (see `benchmarks/hendrix_vs_grover.py` and `turing_universal_quantum_computer/.../hendrix.py`, which are standalone, not tensor-contract consumers). Add a bridge here if/when such an entry point is identified as in-scope. |
| `vqc_manifold_bridge` | not_implemented | — | `Intelligence/asi/manifold_bridge.py` and `toe/manifold_bridge.py` exist but are advisory ASI/TOE surfaces, not tensor execution entry points; no production consumer imports them through a tensor contract today. |

## External hardware gates (not closeable from this repository)

- **Chronus/OpenCL tensor kernels**: no generic tensor compute kernel exists
  in `chronus/kernels/`; it is specialised for SHA-256d search. A real
  hardware-backed tensor backend needs (a) a physical OpenCL device and
  (b) new Chronus kernels, neither of which this change fabricates.
- **Apple/CUDA/ROCm accelerators**: declared as optional extras elsewhere in
  `pyproject.toml` (`apple`, `hardware`) but out of scope for this package's
  backend registry until a concrete, testable adapter is written.
