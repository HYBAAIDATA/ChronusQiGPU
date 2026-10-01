"""Machine-readable evidence manifest for the Tensor package."""
from __future__ import annotations
from typing import Any, Dict

CAPABILITY_MANIFEST: Dict[str, Dict[str, Any]]={
"contracts.validation":{"status":"implemented_tested","implementation":"tensor/contracts.py","tests":"tests/test_tensor_contracts.py"},
"backend.numpy_reference":{"status":"implemented_tested","implementation":"tensor/backends/numpy_backend.py","tests":"tests/test_tensor_backends.py"},
"backend.chronus_adapter":{"status":"hardware_evidence_required","implementation":"tensor/backends/chronus_backend.py + chronus/tensor_compute.py + chronus/kernels/tensor_ops.cl","tests":"tests/test_chronus_tensor_compute.py","evidence_needed":"Physical OpenCL GPU numerical comparison against NumPy reference."},
"hardware.chronus_tensor_kernels":{"status":"hardware_evidence_required","implementation":"chronus/kernels/tensor_ops.cl; chronus/tensor_compute.py","tests":"tests/test_chronus_tensor_compute.py","evidence_needed":"Physical float32 matmul/add/hadamard/scale/kron run with TensorMeasurement/provenance."},
"router.explicit_backend_fail_closed":{"status":"implemented_tested","implementation":"tensor/router.py","tests":"tests/test_tensor_backends.py"},
"router.policy_gated_fallback":{"status":"implemented_tested","implementation":"tensor/router.py","tests":"tests/test_tensor_backends.py"},
"runtime.timing_cancellation_memory":{"status":"implemented_tested","implementation":"tensor/runtime.py","tests":"tests/test_tensor_runtime.py"},
"tflops.declared_op_count_only":{"status":"implemented_tested","implementation":"tensor/contracts.py:TensorMeasurement","tests":"tests/test_tensor_contracts.py"},
"exact.kellogg_exact_tensor":{"status":"implemented_tested","implementation":"kellogg/exact_tensor.py via tensor/kellogg_bridge.py","tests":"tests/test_kellogg_tensor.py"},
"exact.kellogg_quantum_tensor":{"status":"implemented_tested","implementation":"kellogg/quantum_tensor.py via tensor/kellogg_bridge.py","tests":"tests/test_kellogg_tensor.py"},
"exact.kellogg_tensor_ml":{"status":"implemented_tested","implementation":"kellogg/tensor_ml.py via tensor/kellogg_bridge.py","tests":"tests/test_toe_tensor_ml.py"},
"pulvini.exact_geodesic_engine":{"status":"implemented_tested","implementation":"python_backend/core_modules/geodesic_tensor_engine.py","tests":"tests/test_geodesic_tensor_engine.py, tests/test_geodesic_tensor_extensions.py"},
"pulvini.true_partial_unfold":{"status":"implemented_tested","implementation":"python_backend/core_modules/geodesic_tensor_engine.py:unfold_partial","tests":"tests/test_geodesic_tensor_extensions.py"},
"geodesic.metric_energy_virtual_gpu":{"status":"implemented_tested","implementation":"python_backend/core_modules/geodesic_tensor_engine.py","tests":"tests/test_geodesic_tensor_extensions.py"},
"hybrid.profiled_router":{"status":"implemented_tested","implementation":"tensor/hybrid.py:ProfiledHybridRouter","tests":"tests/test_tensor_hybrid_router.py"},
"inference.folded_linear_pilot":{"status":"implemented_tested","implementation":"tensor/folded_inference.py","tests":"tests/test_folded_inference.py","claim_boundary":"Exact reversible custody + measured inference; no physical compression ratio without physical evidence."},
"vqc.exact_and_quantum_tensor_loaders":{"status":"implemented_tested","implementation":"tensor/kellogg_bridge.py","tests":"tests/test_tensor_package.py"},
"mining.advisor_boundary":{"status":"implemented_tested","implementation":"hyba/hybrid/tensor_advisor.py","tests":"tests/test_three_layer_runtime.py, tests/test_tensor_advisor_safety.py"},
"compat.gpu_tensor_shim":{"status":"implemented_tested","implementation":"gpu/tensor.py","tests":"tests/test_tensor_gpu_compat.py"},
"packaging.tensor_distribution":{"status":"implemented_tested","implementation":"pyproject.toml","tests":"tests/test_package_layout.py"},
"grover.hendrix_entry_points":{"status":"not_implemented","implementation":None,"evidence_needed":"Turing Hendrix/Grover exists; wire only for a concrete Tensor production consumer."},
"vqc_manifold_bridge":{"status":"not_implemented","implementation":None,"evidence_needed":"ASI/TOE manifold bridges are advisory, not Tensor execution entry points."},
}


def render_markdown()->str:
    lines=["| Feature | Status | Implementation | Tests/Evidence |","|---|---|---|---|"]
    for feature,row in CAPABILITY_MANIFEST.items():
        impl=row.get("implementation") or "—"; evidence=row.get("tests") or row.get("evidence_needed") or "—"
        lines.append(f"| `{feature}` | {row['status']} | `{impl}` | {evidence} |")
    return "\n".join(lines)

__all__=["CAPABILITY_MANIFEST","render_markdown"]
